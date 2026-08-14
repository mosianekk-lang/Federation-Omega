from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .models import ContinuationMode, ProviderContinuationRef
from .provider_state import ProviderRunStateConflict, ProviderStateStore
from .runtime import ChatBridgeOmega4


class OpenAIProviderUnavailable(RuntimeError):
    pass


class OpenAIProviderBindingError(RuntimeError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ProviderReadback:
    conversation_id: str
    item_count: int
    items_sha256: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "item_count": self.item_count,
            "items_sha256": self.items_sha256,
        }


def _interruptions_payload(items: Iterable[Any]) -> List[Dict[str, Any]]:
    payload: List[Dict[str, Any]] = []
    for index, item in enumerate(items):
        agent = getattr(item, "agent", None)
        payload.append(
            {
                "index": index,
                "name": getattr(item, "name", "") or getattr(item, "tool_name", ""),
                "arguments": getattr(item, "arguments", None),
                "agent": getattr(agent, "name", "") if agent is not None else "",
            }
        )
    return payload


class OpenAIConversationProvider:
    """OpenAI Conversations binding for the ChatBridge Ω4 durable kernel.

    One run uses one continuation strategy: this adapter is only for
    `OPENAI_CONVERSATION`. It deliberately does not also pass `previous_response_id`
    or a second Agents SDK session.

    OpenAI imports are lazy so the provider-neutral core and its deterministic tests
    remain runnable without provider dependencies or credentials.
    """

    PROVIDER = "openai"
    MODE = ContinuationMode.OPENAI_CONVERSATION

    def __init__(
        self,
        bridge: ChatBridgeOmega4,
        provider_state: ProviderStateStore,
        *,
        model: str,
    ) -> None:
        if not model.strip():
            raise ValueError("an explicit OpenAI model is required for provider-bound execution")
        self.bridge = bridge
        self.provider_state = provider_state
        self.model = model.strip()

    def _sdk(self) -> Dict[str, Any]:
        try:
            from agents import Agent, OpenAIConversationsSession, RunState, Runner
        except Exception as exc:  # pragma: no cover - exercised only in provider environment
            raise OpenAIProviderUnavailable(
                "OpenAI Agents SDK provider dependencies are unavailable"
            ) from exc
        return {
            "Agent": Agent,
            "OpenAIConversationsSession": OpenAIConversationsSession,
            "RunState": RunState,
            "Runner": Runner,
        }

    def _restore_envelope(
        self,
        namespace: str,
        *,
        destination_session_key: str,
        allow_restore_preview: bool,
    ) -> Any:
        envelope = self.bridge.store.restore(
            namespace,
            destination_session_key=destination_session_key,
        )
        if envelope.preview_required and not allow_restore_preview:
            reasons = ",".join(reason.value for reason in envelope.preview_reasons)
            raise OpenAIProviderBindingError(
                f"restore preview required before provider execution: {reasons}"
            )
        if envelope.provider_ref.mode not in (
            ContinuationMode.NONE,
            ContinuationMode.OPENAI_CONVERSATION,
        ):
            raise OpenAIProviderBindingError(
                "namespace is bound to a different mutually-exclusive continuation strategy"
            )
        return envelope

    def _session(self, sdk: Dict[str, Any], provider_ref: ProviderContinuationRef) -> Any:
        session_cls = sdk["OpenAIConversationsSession"]
        if provider_ref.mode is ContinuationMode.NONE:
            return session_cls()
        return session_cls(conversation_id=provider_ref.conversation_id)

    def _agent(
        self,
        sdk: Dict[str, Any],
        *,
        name: str,
        instructions: str,
        tools: Optional[Sequence[Any]] = None,
    ) -> Any:
        return sdk["Agent"](
            name=name,
            instructions=instructions,
            model=self.model,
            tools=list(tools or []),
        )

    async def _readback(self, session: Any, *, limit: int = 100) -> ProviderReadback:
        items = await session.get_items(limit=limit)
        conversation_id = session.session_id
        return ProviderReadback(
            conversation_id=conversation_id,
            item_count=len(items),
            items_sha256=_sha256(items),
        )

    def _bind_new_conversation(self, namespace: str, envelope: Any, conversation_id: str) -> Any:
        provider_ref = ProviderContinuationRef(
            mode=ContinuationMode.OPENAI_CONVERSATION,
            provider=self.PROVIDER,
            conversation_id=conversation_id,
            metadata={"binding": "OPENAI_CONVERSATIONS_SESSION"},
        )
        refreshed = self.bridge.refresh(
            namespace,
            envelope.governance,
            hot_state=envelope.hot_state,
            warm_pointers=envelope.warm_pointers,
            cold_pointers=envelope.cold_pointers,
            provider_ref=provider_ref,
        )
        return self.bridge.store.restore(
            namespace,
            destination_session_key=f"provider-bind:{refreshed['generation_id']}",
        )

    async def run_turn(
        self,
        namespace: str,
        user_input: str,
        *,
        destination_session_key: str,
        agent_name: str = "ChatBridge Ω4 Provider Canary",
        instructions: str = "Maintain the governed conversation faithfully and concisely.",
        tools: Optional[Sequence[Any]] = None,
        allow_restore_preview: bool = False,
    ) -> Dict[str, Any]:
        sdk = self._sdk()
        envelope = self._restore_envelope(
            namespace,
            destination_session_key=destination_session_key,
            allow_restore_preview=allow_restore_preview,
        )
        session = self._session(sdk, envelope.provider_ref)
        agent = self._agent(sdk, name=agent_name, instructions=instructions, tools=tools)

        result = await sdk["Runner"].run(agent, user_input, session=session)
        readback = await self._readback(session)

        if envelope.provider_ref.mode is ContinuationMode.NONE:
            envelope = self._bind_new_conversation(namespace, envelope, readback.conversation_id)
        elif envelope.provider_ref.conversation_id != readback.conversation_id:
            raise OpenAIProviderBindingError("provider conversation identity drift detected")

        interruptions = _interruptions_payload(result.interruptions)
        run_state_id = ""
        semantic_state = "TURN_COMPLETE_READBACK_VERIFIED"
        if result.interruptions:
            state = result.to_state()
            persisted = self.provider_state.save_run_state(
                namespace_id=envelope.namespace_id,
                generation_id=envelope.generation_id,
                handoff_id=envelope.handoff_id,
                checkpoint_fingerprint=envelope.checkpoint_fingerprint,
                provider=self.PROVIDER,
                continuation_id=readback.conversation_id,
                state_json=state.to_string(),
                interruptions=interruptions,
            )
            run_state_id = persisted["run_state_id"]
            semantic_state = "INTERRUPTED_WAITING_APPROVAL"

        final_output = "" if result.final_output is None else str(result.final_output)
        receipt = self.provider_state.save_receipt(
            namespace_id=envelope.namespace_id,
            generation_id=envelope.generation_id,
            handoff_id=envelope.handoff_id,
            checkpoint_fingerprint=envelope.checkpoint_fingerprint,
            provider=self.PROVIDER,
            continuation_mode=self.MODE.value,
            continuation_id=readback.conversation_id,
            response_id=getattr(result, "last_response_id", "") or "",
            operation="RUN_TURN",
            semantic_state=semantic_state,
            output_text=final_output,
            run_state_id=run_state_id,
            metadata={
                "provider_readback": readback.to_dict(),
                "interruptions": interruptions,
                "model": self.model,
            },
        )
        return {
            "state": semantic_state,
            "namespace": namespace,
            "namespace_id": envelope.namespace_id,
            "generation_id": envelope.generation_id,
            "generation_number": envelope.generation_number,
            "handoff_id": envelope.handoff_id,
            "checkpoint_fingerprint": envelope.checkpoint_fingerprint,
            "conversation_id": readback.conversation_id,
            "response_id": getattr(result, "last_response_id", "") or "",
            "provider_readback": readback.to_dict(),
            "final_output": final_output,
            "interruptions": interruptions,
            "run_state_id": run_state_id,
            "receipt": receipt.to_dict(),
        }

    async def resume_approval(
        self,
        namespace: str,
        run_state_id: str,
        decisions: Sequence[bool],
        *,
        destination_session_key: str,
        agent_name: str = "ChatBridge Ω4 Provider Canary",
        instructions: str = "Maintain the governed conversation faithfully and concisely.",
        tools: Optional[Sequence[Any]] = None,
        allow_restore_preview: bool = False,
    ) -> Dict[str, Any]:
        sdk = self._sdk()
        envelope = self._restore_envelope(
            namespace,
            destination_session_key=destination_session_key,
            allow_restore_preview=allow_restore_preview,
        )
        if envelope.provider_ref.mode is not ContinuationMode.OPENAI_CONVERSATION:
            raise OpenAIProviderBindingError("approval resume requires an OpenAI conversation binding")

        claimed = self.provider_state.claim_run_state(run_state_id)
        token = claimed["fencing_token"]
        if (
            claimed["namespace_id"] != envelope.namespace_id
            or claimed["generation_id"] != envelope.generation_id
            or claimed["checkpoint_fingerprint"] != envelope.checkpoint_fingerprint
            or claimed["continuation_id"] != envelope.provider_ref.conversation_id
        ):
            self.provider_state.release_claim(run_state_id, token)
            raise OpenAIProviderBindingError("RunState binding does not match restored namespace generation")

        agent = self._agent(sdk, name=agent_name, instructions=instructions, tools=tools)
        session = self._session(sdk, envelope.provider_ref)
        try:
            state = await sdk["RunState"].from_string(agent, claimed["state_json"])
            interruptions = list(state.get_interruptions())
            if len(decisions) != len(interruptions):
                raise OpenAIProviderBindingError(
                    "approval decisions must exactly cover the persisted interruption set"
                )
            for interruption, approved in zip(interruptions, decisions):
                if approved:
                    state.approve(interruption, always_approve=False)
                else:
                    state.reject(interruption)

            result = await sdk["Runner"].run(agent, state, session=session)
            readback = await self._readback(session)
            if readback.conversation_id != envelope.provider_ref.conversation_id:
                raise OpenAIProviderBindingError("provider conversation identity drift detected after resume")

            next_interruptions = _interruptions_payload(result.interruptions)
            next_run_state_id = ""
            semantic_state = "APPROVAL_RESUME_COMPLETE_READBACK_VERIFIED"
            if result.interruptions:
                next_state = result.to_state()
                persisted = self.provider_state.save_run_state(
                    namespace_id=envelope.namespace_id,
                    generation_id=envelope.generation_id,
                    handoff_id=envelope.handoff_id,
                    checkpoint_fingerprint=envelope.checkpoint_fingerprint,
                    provider=self.PROVIDER,
                    continuation_id=readback.conversation_id,
                    state_json=next_state.to_string(),
                    interruptions=next_interruptions,
                )
                next_run_state_id = persisted["run_state_id"]
                semantic_state = "RESUMED_THEN_INTERRUPTED_WAITING_APPROVAL"

            final_output = "" if result.final_output is None else str(result.final_output)
            receipt = self.provider_state.save_receipt(
                namespace_id=envelope.namespace_id,
                generation_id=envelope.generation_id,
                handoff_id=envelope.handoff_id,
                checkpoint_fingerprint=envelope.checkpoint_fingerprint,
                provider=self.PROVIDER,
                continuation_mode=self.MODE.value,
                continuation_id=readback.conversation_id,
                response_id=getattr(result, "last_response_id", "") or "",
                operation="RESUME_APPROVAL",
                semantic_state=semantic_state,
                output_text=final_output,
                run_state_id=next_run_state_id,
                metadata={
                    "provider_readback": readback.to_dict(),
                    "decisions": [bool(v) for v in decisions],
                    "next_interruptions": next_interruptions,
                    "model": self.model,
                },
            )
            self.provider_state.mark_resumed(run_state_id, token, receipt.receipt_id)
            return {
                "state": semantic_state,
                "namespace": namespace,
                "conversation_id": readback.conversation_id,
                "response_id": getattr(result, "last_response_id", "") or "",
                "provider_readback": readback.to_dict(),
                "final_output": final_output,
                "interruptions": next_interruptions,
                "run_state_id": next_run_state_id,
                "receipt": receipt.to_dict(),
            }
        except Exception:
            current = self.provider_state.get_run_state(run_state_id)
            if current["status"] == "CLAIMED" and current["fencing_token"] == token:
                self.provider_state.release_claim(run_state_id, token)
            raise
