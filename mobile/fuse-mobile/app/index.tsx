import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Platform,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  useWindowDimensions,
  View,
} from 'react-native';

import {
  federationGatewayConfigured,
  type FuseChatResponse,
  type FuseMode,
} from '../src/federation';
import { iapConfigured } from '../src/iap';
import { connectOwner, restoreOwnerSession, sendOwnerFuseMessage } from '../src/ownerConnection';
import type { StoredSession } from '../src/session';
import { AegisSecurityCheckCard } from '../src/AegisSecurityCheckCard';
import { capabilityPassportSummary } from '../src/cfbeCapabilityPassport';

const modes: FuseMode[] = ['AUTO', 'FAST', 'THINK', 'CREATE', 'BUILD', 'RESEARCH', 'EXECUTE', 'PRIVATE'];
const promptStarters: Array<{ label: string; mode: FuseMode; prompt: string }> = [
  { label: 'Research', mode: 'RESEARCH', prompt: 'Research this deeply, cite evidence, identify contradictions, and recommend the strongest next action: ' },
  { label: 'Build', mode: 'BUILD', prompt: 'Build the smallest production-grade solution that closes this goal completely: ' },
  { label: 'Create', mode: 'CREATE', prompt: 'Create three high-quality directions, compare them, and continue with the strongest: ' },
  { label: 'Execute', mode: 'EXECUTE', prompt: 'Execute the authorized work with proof-before-claim and return provider readback: ' },
];

type UiState = 'READY' | 'SESSION_REQUIRED' | 'CONNECTING' | 'SENDING' | 'ERROR' | 'CANCELLED';
type TimelineEvent = { id: number; label: string; detail: string };

function errorMessage(error: unknown): string {
  if (error instanceof Error) {
    if (error.name === 'AbortError') return 'REQUEST_CANCELLED';
    return error.message;
  }
  return 'FUSE_REQUEST_FAILED';
}

export default function Home() {
  const { width } = useWindowDimensions();
  const wide = width >= 900;
  const inputRef = useRef<TextInput>(null);
  const activeRequest = useRef<AbortController | null>(null);
  const timelineCounter = useRef(0);
  const [mode, setMode] = useState<FuseMode>('AUTO');
  const [text, setText] = useState('');
  const [session, setSession] = useState<StoredSession | null>(null);
  const [uiState, setUiState] = useState<UiState>('SESSION_REQUIRED');
  const [response, setResponse] = useState<FuseChatResponse | null>(null);
  const [message, setMessage] = useState('');
  const [lastLatencyMs, setLastLatencyMs] = useState<number | null>(null);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const passport = useMemo(() => capabilityPassportSummary(), []);
  const gatewayReady = federationGatewayConfigured();
  const identityReady = iapConfigured();
  const canSend = useMemo(
    () => text.trim().length > 0 && uiState === 'READY',
    [text, uiState],
  );

  function record(label: string, detail: string) {
    timelineCounter.current += 1;
    const item = { id: timelineCounter.current, label, detail };
    setTimeline((current) => [item, ...current].slice(0, 6));
  }

  useEffect(() => {
    let active = true;
    restoreOwnerSession()
      .then((loaded) => {
        if (!active) return;
        setSession(loaded);
        const ready = Boolean(loaded && gatewayReady && identityReady);
        setUiState(ready ? 'READY' : 'SESSION_REQUIRED');
        record('Session restore', ready ? 'Owner session restored.' : 'Interactive owner connection required.');
      })
      .catch(() => {
        if (!active) return;
        setUiState('SESSION_REQUIRED');
        record('Session restore', 'No reusable owner session found.');
      });
    return () => {
      active = false;
      activeRequest.current?.abort();
    };
  }, [gatewayReady, identityReady]);

  useEffect(() => {
    if (Platform.OS !== 'web' || typeof window === 'undefined') return;
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        inputRef.current?.focus();
      }
      if (event.key === 'Escape' && activeRequest.current) {
        activeRequest.current.abort();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  async function handleConnect() {
    if (uiState === 'CONNECTING') return;
    if (!gatewayReady || !identityReady) {
      setMessage('FUSE gateway or owner identity is not configured in this build.');
      setUiState('ERROR');
      record('Connection blocked', 'Required public runtime configuration is missing.');
      return;
    }
    setUiState('CONNECTING');
    setMessage('');
    setResponse(null);
    record('Owner connect', 'Starting governed owner identity flow.');
    try {
      const connected = await connectOwner();
      setSession(connected);
      setMessage('Owner connection verified. FUSE is ready.');
      setUiState('READY');
      record('Owner connect', 'Identity and FUSE session established.');
    } catch (error) {
      setSession(null);
      const detail = errorMessage(error);
      setMessage(detail);
      setUiState('SESSION_REQUIRED');
      record('Owner connect failed', detail);
    }
  }

  async function handleSend() {
    const intent = text.trim();
    if (!intent || uiState !== 'READY') return;
    if (!session || !gatewayReady || !identityReady) {
      setUiState('SESSION_REQUIRED');
      setMessage('Connect the owner identity before FUSE can execute this request.');
      return;
    }

    const controller = new AbortController();
    activeRequest.current = controller;
    const started = Date.now();
    setUiState('SENDING');
    setMessage('');
    setResponse(null);
    record('Request accepted', `${mode} · verification ${mode === 'FAST' ? 'NORMAL' : 'HIGH'}`);
    try {
      const next = await sendOwnerFuseMessage({
        intent,
        mode,
        verification: mode === 'FAST' ? 'NORMAL' : 'HIGH',
      }, controller.signal);
      const elapsed = Date.now() - started;
      setResponse(next);
      setLastLatencyMs(elapsed);
      setText('');
      setUiState('READY');
      record('Provider readback', `${next.status ?? 'OK'} · ${elapsed} ms${next.trace_id ? ` · trace ${next.trace_id}` : ''}`);
    } catch (error) {
      const detail = controller.signal.aborted ? 'REQUEST_CANCELLED' : errorMessage(error);
      setLastLatencyMs(Date.now() - started);
      setMessage(detail);
      setUiState(controller.signal.aborted ? 'CANCELLED' : 'ERROR');
      record(controller.signal.aborted ? 'Request cancelled' : 'Request failed', detail);
    } finally {
      if (activeRequest.current === controller) activeRequest.current = null;
    }
  }

  function handleStop() {
    activeRequest.current?.abort();
  }

  function selectStarter(item: (typeof promptStarters)[number]) {
    setMode(item.mode);
    setText(item.prompt);
    inputRef.current?.focus();
  }

  const statusText = uiState === 'READY'
    ? 'Private owner session ready'
    : uiState === 'CONNECTING'
      ? 'Verifying owner identity…'
      : uiState === 'SENDING'
        ? 'FUSE is working…'
        : uiState === 'CANCELLED'
          ? 'Request cancelled — ready to revise'
          : uiState === 'ERROR'
            ? 'Gateway request needs attention'
            : 'Owner connection required';

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={[styles.shell, wide && styles.shellWide]} keyboardShouldPersistTaps="handled">
        <View style={styles.brandRow}>
          <View style={styles.pulse} />
          <Text style={styles.brand}>FUSE</Text>
          <Text style={styles.owner}>Ω</Text>
          <View style={styles.spacer} />
          <View style={styles.passportBadge} accessibilityLabel={`${passport.total} CFBE improvements tracked`}>
            <Text style={styles.passportText}>CFBE {passport.total}</Text>
          </View>
        </View>
        <Text style={styles.status}>{statusText}</Text>

        <View style={[styles.topGrid, wide && styles.topGridWide]}>
          <View style={styles.heroPane}>
            <Text style={[styles.hero, wide && styles.heroWide]}>One workspace. Federation power.</Text>
            <Text style={styles.subhero}>Research, create, build and execute with visible authority, trace and proof.</Text>

            {uiState === 'SESSION_REQUIRED' || !session ? (
              <Pressable accessibilityRole="button" accessibilityLabel="Connect FUSE owner identity" onPress={handleConnect} style={styles.connect}>
                <Text style={styles.connectText}>Connect owner</Text>
              </Pressable>
            ) : null}
          </View>

          <View style={[styles.diagnostics, wide && styles.diagnosticsWide]}>
            <Text style={styles.sectionEyebrow}>LIVE DIAGNOSTICS</Text>
            <Diagnostic label="Gateway" value={gatewayReady ? 'configured' : 'missing config'} ok={gatewayReady} />
            <Diagnostic label="Owner identity" value={identityReady ? 'configured' : 'missing config'} ok={identityReady} />
            <Diagnostic label="Session" value={session ? 'available' : 'not connected'} ok={Boolean(session)} />
            <Diagnostic label="Last latency" value={lastLatencyMs === null ? '—' : `${lastLatencyMs} ms`} ok={lastLatencyMs !== null} />
            <Diagnostic label="CFBE passport" value={`${passport.P0} P0 · ${passport.P1} P1 · ${passport.P2} P2`} ok />
          </View>
        </View>

        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.modeRow}>
          {modes.map((item) => (
            <Pressable
              accessibilityRole="button"
              accessibilityState={{ selected: item === mode }}
              key={item}
              onPress={() => setMode(item)}
              style={[styles.mode, item === mode && styles.modeActive]}
            >
              <Text style={[styles.modeText, item === mode && styles.modeTextActive]}>{item}</Text>
            </Pressable>
          ))}
        </ScrollView>

        <View style={styles.starterRow}>
          {promptStarters.map((item) => (
            <Pressable key={item.label} onPress={() => selectStarter(item)} style={styles.starter} accessibilityRole="button">
              <Text style={styles.starterText}>{item.label}</Text>
            </Pressable>
          ))}
        </View>

        <View style={styles.composer}>
          <TextInput
            ref={inputRef}
            multiline
            value={text}
            onChangeText={setText}
            placeholder="Ask FUSE anything…"
            placeholderTextColor="#777"
            style={styles.input}
            accessibilityLabel="FUSE request"
          />
          <View style={styles.composerFooter}>
            <View style={styles.tool}><Text style={styles.toolText}>＋</Text></View>
            <Text style={styles.modeHint}>{mode} · {mode === 'FAST' ? 'normal' : 'high'} verification</Text>
            {uiState === 'SENDING' ? (
              <Pressable onPress={handleStop} style={styles.stop} accessibilityRole="button" accessibilityLabel="Stop current FUSE request">
                <Text style={styles.stopText}>Stop</Text>
              </Pressable>
            ) : (
              <Pressable onPress={handleSend} disabled={!canSend} style={[styles.send, !canSend && styles.sendDisabled]} accessibilityRole="button" accessibilityLabel="Send to FUSE">
                <Text style={styles.sendText}>↑</Text>
              </Pressable>
            )}
          </View>
          {Platform.OS === 'web' ? <Text style={styles.shortcut}>⌘/Ctrl K focuses · Esc stops</Text> : null}
        </View>

        {mode === 'EXECUTE' ? (
          <View style={styles.effectPreview}>
            <Text style={styles.effectTitle}>Authority preview</Text>
            <Text style={styles.effectText}>EXECUTE requests still pass Federation effect gates. The client does not grant provider, IAM, secret, spend or production authority by itself.</Text>
          </View>
        ) : null}

        {response ? (
          <View style={styles.resultCard}>
            <Text style={styles.sectionEyebrow}>PROVIDER READBACK</Text>
            <Text selectable style={styles.resultText}>{response.text}</Text>
            <View style={styles.metaRow}>
              {response.provider ? <MetaPill text={response.provider} /> : null}
              {response.model ? <MetaPill text={response.model} /> : null}
              {response.status ? <MetaPill text={response.status} /> : null}
            </View>
            {response.source_refs?.length ? (
              <View style={styles.sources}>
                <Text style={styles.sourceTitle}>Sources</Text>
                {response.source_refs.map((ref) => <Text selectable key={ref} style={styles.sourceRef}>{ref}</Text>)}
              </View>
            ) : null}
            {response.trace_id ? <Text selectable style={styles.trace}>Trace {response.trace_id}</Text> : null}
          </View>
        ) : null}

        {message ? (
          <View style={styles.notice}>
            <Text selectable style={styles.noticeText}>{message}</Text>
            {(uiState === 'ERROR' || uiState === 'CANCELLED') && session ? (
              <Pressable onPress={() => setUiState('READY')} style={styles.recover} accessibilityRole="button">
                <Text style={styles.recoverText}>Return to composer</Text>
              </Pressable>
            ) : null}
          </View>
        ) : null}

        <View style={[styles.lowerGrid, wide && styles.lowerGridWide]}>
          <View style={styles.timelineCard}>
            <Text style={styles.sectionEyebrow}>ACTION TIMELINE</Text>
            {timeline.length === 0 ? <Text style={styles.muted}>No actions yet.</Text> : timeline.map((item) => (
              <View key={item.id} style={styles.timelineItem}>
                <View style={styles.timelineDot} />
                <View style={styles.timelineCopy}>
                  <Text style={styles.timelineLabel}>{item.label}</Text>
                  <Text style={styles.timelineDetail}>{item.detail}</Text>
                </View>
              </View>
            ))}
          </View>
          <View style={styles.securityPane}>
            <AegisSecurityCheckCard />
          </View>
        </View>

        <View style={styles.quickGrid}>
          {[
            ['Federation', 'Capabilities, agents and providers'],
            ['Creative', 'Design, variants and artifact work'],
            ['Research', 'Evidence, citations and synthesis'],
            ['Workspace', 'Projects, files and execution history'],
          ].map(([label, detail]) => (
            <Pressable key={label} style={[styles.quickCard, wide && styles.quickCardWide]} accessibilityRole="button">
              <Text style={styles.quickText}>{label}</Text>
              <Text style={styles.quickDetail}>{detail}</Text>
            </Pressable>
          ))}
        </View>

        <Text style={styles.proofFooter}>Proof-before-claim · F226 source candidate · runtime promotion requires host and provider readback.</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

function Diagnostic({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <View style={styles.diagnosticRow}>
      <View style={[styles.diagnosticDot, ok && styles.diagnosticDotOk]} />
      <Text style={styles.diagnosticLabel}>{label}</Text>
      <Text style={styles.diagnosticValue}>{value}</Text>
    </View>
  );
}

function MetaPill({ text }: { text: string }) {
  return <View style={styles.metaPill}><Text style={styles.metaText}>{text}</Text></View>;
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#090A0C' },
  shell: { flexGrow: 1, width: '100%', paddingHorizontal: 20, paddingTop: 24, paddingBottom: 44 },
  shellWide: { maxWidth: 1180, alignSelf: 'center', paddingHorizontal: 32 },
  brandRow: { flexDirection: 'row', alignItems: 'center', gap: 9 },
  pulse: { width: 12, height: 12, borderRadius: 6, backgroundColor: '#F5F7FF' },
  brand: { color: '#F5F7FF', fontSize: 20, fontWeight: '700', letterSpacing: 3 },
  owner: { color: '#8D93A1', fontSize: 16 },
  spacer: { flex: 1 },
  passportBadge: { borderWidth: 1, borderColor: '#333844', borderRadius: 18, paddingHorizontal: 12, paddingVertical: 7, backgroundColor: '#111318' },
  passportText: { color: '#C9CED8', fontSize: 11, fontWeight: '700', letterSpacing: 0.5 },
  status: { color: '#7F8795', fontSize: 12, marginTop: 10 },
  topGrid: { marginTop: 42 },
  topGridWide: { flexDirection: 'row', gap: 28, alignItems: 'stretch' },
  heroPane: { flex: 1 },
  hero: { color: '#F5F7FF', fontSize: 36, lineHeight: 42, fontWeight: '600', maxWidth: 500 },
  heroWide: { fontSize: 54, lineHeight: 59, maxWidth: 680 },
  subhero: { color: '#9299A6', fontSize: 16, lineHeight: 24, marginTop: 16, maxWidth: 610 },
  connect: { marginTop: 22, alignSelf: 'flex-start', borderRadius: 20, backgroundColor: '#F5F7FF', paddingHorizontal: 18, paddingVertical: 10 },
  connectText: { color: '#111216', fontSize: 13, fontWeight: '700' },
  diagnostics: { marginTop: 24, borderRadius: 22, borderWidth: 1, borderColor: '#242832', backgroundColor: '#101217', padding: 16 },
  diagnosticsWide: { width: 340, marginTop: 0 },
  sectionEyebrow: { color: '#757D8C', fontSize: 10, fontWeight: '800', letterSpacing: 1.4, marginBottom: 12 },
  diagnosticRow: { flexDirection: 'row', alignItems: 'center', minHeight: 29 },
  diagnosticDot: { width: 7, height: 7, borderRadius: 4, backgroundColor: '#5A3F42', marginRight: 9 },
  diagnosticDotOk: { backgroundColor: '#DDE5DA' },
  diagnosticLabel: { color: '#AAB0BC', fontSize: 12, flex: 1 },
  diagnosticValue: { color: '#717988', fontSize: 11, marginLeft: 8 },
  modeRow: { gap: 8, paddingVertical: 26 },
  mode: { borderWidth: 1, borderColor: '#282B31', borderRadius: 20, paddingHorizontal: 14, paddingVertical: 8 },
  modeActive: { backgroundColor: '#F5F7FF', borderColor: '#F5F7FF' },
  modeText: { color: '#9CA1AC', fontSize: 12, fontWeight: '600' },
  modeTextActive: { color: '#111216' },
  starterRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 12 },
  starter: { borderRadius: 14, backgroundColor: '#151820', paddingHorizontal: 12, paddingVertical: 8, borderWidth: 1, borderColor: '#252A34' },
  starterText: { color: '#AEB5C2', fontSize: 11, fontWeight: '600' },
  composer: { borderWidth: 1, borderColor: '#303540', borderRadius: 24, backgroundColor: '#121419', minHeight: 176, padding: 16 },
  input: { color: '#F5F7FF', minHeight: 96, fontSize: 18, lineHeight: 26, textAlignVertical: 'top' },
  composerFooter: { flexDirection: 'row', alignItems: 'center', marginTop: 8 },
  tool: { width: 40, height: 40, borderRadius: 20, backgroundColor: '#20232A', alignItems: 'center', justifyContent: 'center' },
  toolText: { color: '#F5F7FF', fontSize: 24, marginTop: -2 },
  modeHint: { color: '#747A87', fontSize: 11, marginLeft: 12, flex: 1 },
  send: { width: 42, height: 42, borderRadius: 21, backgroundColor: '#F5F7FF', alignItems: 'center', justifyContent: 'center' },
  sendDisabled: { opacity: 0.28 },
  sendText: { color: '#111216', fontSize: 25, fontWeight: '700', marginTop: -3 },
  stop: { minWidth: 70, height: 42, borderRadius: 21, backgroundColor: '#2A1E21', borderWidth: 1, borderColor: '#6F4A51', alignItems: 'center', justifyContent: 'center', paddingHorizontal: 14 },
  stopText: { color: '#E7C8CE', fontSize: 12, fontWeight: '700' },
  shortcut: { color: '#5E6572', fontSize: 10, marginTop: 10 },
  effectPreview: { marginTop: 12, borderRadius: 16, borderWidth: 1, borderColor: '#39404D', backgroundColor: '#12161D', padding: 14 },
  effectTitle: { color: '#D8DCE4', fontSize: 12, fontWeight: '700' },
  effectText: { color: '#868E9C', fontSize: 12, lineHeight: 18, marginTop: 5 },
  resultCard: { marginTop: 18, borderRadius: 20, borderWidth: 1, borderColor: '#252932', backgroundColor: '#101217', padding: 18 },
  resultText: { color: '#E7E9EE', fontSize: 15, lineHeight: 23 },
  metaRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 7, marginTop: 14 },
  metaPill: { borderRadius: 12, backgroundColor: '#1B1F27', paddingHorizontal: 9, paddingVertical: 5 },
  metaText: { color: '#8F97A6', fontSize: 10 },
  sources: { marginTop: 14, borderTopWidth: 1, borderTopColor: '#232833', paddingTop: 12 },
  sourceTitle: { color: '#AAB0BC', fontSize: 11, fontWeight: '700', marginBottom: 6 },
  sourceRef: { color: '#707988', fontSize: 10, lineHeight: 15 },
  trace: { color: '#69707D', fontSize: 10, marginTop: 12 },
  notice: { marginTop: 14, borderRadius: 16, borderWidth: 1, borderColor: '#3A3034', backgroundColor: '#171316', padding: 14 },
  noticeText: { color: '#D6CBD0', fontSize: 12, lineHeight: 18 },
  recover: { alignSelf: 'flex-start', marginTop: 10, borderRadius: 14, backgroundColor: '#252931', paddingHorizontal: 12, paddingVertical: 8 },
  recoverText: { color: '#D0D5DE', fontSize: 11, fontWeight: '700' },
  lowerGrid: { marginTop: 22, gap: 16 },
  lowerGridWide: { flexDirection: 'row', alignItems: 'flex-start' },
  timelineCard: { flex: 1, borderRadius: 20, borderWidth: 1, borderColor: '#242832', backgroundColor: '#0F1116', padding: 16 },
  timelineItem: { flexDirection: 'row', paddingVertical: 8 },
  timelineDot: { width: 7, height: 7, borderRadius: 4, backgroundColor: '#A7AFBD', marginTop: 5, marginRight: 10 },
  timelineCopy: { flex: 1 },
  timelineLabel: { color: '#C8CDD6', fontSize: 12, fontWeight: '700' },
  timelineDetail: { color: '#707988', fontSize: 11, lineHeight: 16, marginTop: 2 },
  muted: { color: '#626A77', fontSize: 12 },
  securityPane: { flex: 1 },
  quickGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginTop: 22 },
  quickCard: { width: '48%', minHeight: 86, paddingVertical: 16, paddingHorizontal: 16, borderRadius: 18, backgroundColor: '#111318', borderWidth: 1, borderColor: '#22252B' },
  quickCardWide: { width: '24%' },
  quickText: { color: '#C7CBD3', fontSize: 14, fontWeight: '600' },
  quickDetail: { color: '#6E7581', fontSize: 11, lineHeight: 16, marginTop: 5 },
  proofFooter: { color: '#515865', fontSize: 10, lineHeight: 15, marginTop: 26, textAlign: 'center' },
});
