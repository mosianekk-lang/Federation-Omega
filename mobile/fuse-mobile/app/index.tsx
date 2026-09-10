import { useEffect, useMemo, useState } from 'react';
import { Pressable, SafeAreaView, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

import { federationGatewayConfigured, type FuseMode } from '../src/federation';
import { iapConfigured } from '../src/iap';
import { connectOwner, restoreOwnerSession, sendOwnerFuseMessage } from '../src/ownerConnection';
import type { StoredSession } from '../src/session';
import { AegisSecurityCheckCard } from '../src/AegisSecurityCheckCard';

const modes: FuseMode[] = ['AUTO', 'THINK', 'CREATE', 'BUILD', 'RESEARCH'];

type UiState = 'READY' | 'SESSION_REQUIRED' | 'CONNECTING' | 'SENDING' | 'ERROR';

export default function Home() {
  const [mode, setMode] = useState<FuseMode>('AUTO');
  const [text, setText] = useState('');
  const [session, setSession] = useState<StoredSession | null>(null);
  const [uiState, setUiState] = useState<UiState>('SESSION_REQUIRED');
  const [result, setResult] = useState('');
  const [traceId, setTraceId] = useState<string | undefined>();
  const canSend = useMemo(
    () => text.trim().length > 0 && uiState === 'READY',
    [text, uiState],
  );

  useEffect(() => {
    let active = true;
    restoreOwnerSession()
      .then((loaded) => {
        if (!active) return;
        setSession(loaded);
        setUiState(loaded && federationGatewayConfigured() && iapConfigured() ? 'READY' : 'SESSION_REQUIRED');
      })
      .catch(() => {
        if (active) setUiState('SESSION_REQUIRED');
      });
    return () => {
      active = false;
    };
  }, []);

  async function handleConnect() {
    if (uiState === 'CONNECTING') return;
    if (!federationGatewayConfigured() || !iapConfigured()) {
      setResult('FUSE private gateway transport is not configured in this build.');
      setUiState('ERROR');
      return;
    }
    setUiState('CONNECTING');
    setResult('');
    setTraceId(undefined);
    try {
      const connected = await connectOwner();
      setSession(connected);
      setResult('Owner connection verified. FUSE is ready.');
      setUiState('READY');
    } catch (error) {
      setSession(null);
      setResult(error instanceof Error ? error.message : 'OWNER_CONNECTION_FAILED');
      setUiState('SESSION_REQUIRED');
    }
  }

  async function handleSend() {
    const intent = text.trim();
    if (!intent || uiState !== 'READY') return;
    if (!session || !federationGatewayConfigured() || !iapConfigured()) {
      setUiState('SESSION_REQUIRED');
      setResult('Connect the owner identity before FUSE can execute this request.');
      return;
    }

    setUiState('SENDING');
    setResult('');
    setTraceId(undefined);
    try {
      const response = await sendOwnerFuseMessage({
        intent,
        mode,
        verification: mode === 'FAST' ? 'NORMAL' : 'HIGH',
      });
      setResult(response.text);
      setTraceId(response.trace_id);
      setText('');
      setUiState('READY');
    } catch (error) {
      setResult(error instanceof Error ? error.message : 'FUSE_REQUEST_FAILED');
      setUiState('ERROR');
    }
  }

  const statusText = uiState === 'READY'
    ? 'Private owner session ready'
    : uiState === 'CONNECTING'
      ? 'Verifying owner identity…'
      : uiState === 'SENDING'
        ? 'FUSE is working…'
        : uiState === 'ERROR'
          ? 'Gateway request needs attention'
          : 'Owner connection required';

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.shell} keyboardShouldPersistTaps="handled">
        <View style={styles.brandRow}>
          <View style={styles.pulse} />
          <Text style={styles.brand}>FUSE</Text>
          <Text style={styles.owner}>Ω</Text>
        </View>
        <Text style={styles.status}>{statusText}</Text>
        <Text style={styles.hero}>What are we building today?</Text>

        {uiState === 'SESSION_REQUIRED' || !session ? (
          <Pressable onPress={handleConnect} style={styles.connect}>
            <Text style={styles.connectText}>Connect owner</Text>
          </Pressable>
        ) : null}

        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.modeRow}>
          {modes.map((item) => (
            <Pressable key={item} onPress={() => setMode(item)} style={[styles.mode, item === mode && styles.modeActive]}>
              <Text style={[styles.modeText, item === mode && styles.modeTextActive]}>{item}</Text>
            </Pressable>
          ))}
        </ScrollView>

        <View style={styles.composer}>
          <TextInput
            multiline
            value={text}
            onChangeText={setText}
            placeholder="Ask FUSE anything…"
            placeholderTextColor="#777"
            style={styles.input}
          />
          <View style={styles.composerFooter}>
            <Pressable style={styles.tool}><Text style={styles.toolText}>＋</Text></Pressable>
            <Text style={styles.modeHint}>{mode}</Text>
            <Pressable onPress={handleSend} disabled={!canSend} style={[styles.send, !canSend && styles.sendDisabled]}>
              <Text style={styles.sendText}>↑</Text>
            </Pressable>
          </View>
        </View>

        {result ? (
          <View style={styles.resultCard}>
            <Text style={styles.resultText}>{result}</Text>
            {traceId ? <Text style={styles.trace}>Trace {traceId}</Text> : null}
          </View>
        ) : null}

        <AegisSecurityCheckCard />

        <View style={styles.quickGrid}>
          {['Federation', 'Creative', 'Research', 'Workspace'].map((label) => (
            <Pressable key={label} style={styles.quickCard}><Text style={styles.quickText}>{label}</Text></Pressable>
          ))}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#090A0C' },
  shell: { flexGrow: 1, paddingHorizontal: 20, paddingTop: 24, paddingBottom: 36 },
  brandRow: { flexDirection: 'row', alignItems: 'center', gap: 9 },
  pulse: { width: 12, height: 12, borderRadius: 6, backgroundColor: '#F5F7FF' },
  brand: { color: '#F5F7FF', fontSize: 20, fontWeight: '700', letterSpacing: 3 },
  owner: { color: '#8D93A1', fontSize: 16 },
  status: { color: '#7F8795', fontSize: 12, marginTop: 10 },
  hero: { color: '#F5F7FF', fontSize: 34, lineHeight: 41, fontWeight: '600', marginTop: 58, maxWidth: 330 },
  connect: { marginTop: 22, alignSelf: 'flex-start', borderRadius: 20, backgroundColor: '#F5F7FF', paddingHorizontal: 18, paddingVertical: 10 },
  connectText: { color: '#111216', fontSize: 13, fontWeight: '700' },
  modeRow: { gap: 8, paddingVertical: 26 },
  mode: { borderWidth: 1, borderColor: '#282B31', borderRadius: 20, paddingHorizontal: 14, paddingVertical: 8 },
  modeActive: { backgroundColor: '#F5F7FF', borderColor: '#F5F7FF' },
  modeText: { color: '#9CA1AC', fontSize: 12, fontWeight: '600' },
  modeTextActive: { color: '#111216' },
  composer: { borderWidth: 1, borderColor: '#2B2E35', borderRadius: 24, backgroundColor: '#121419', minHeight: 164, padding: 16 },
  input: { color: '#F5F7FF', minHeight: 92, fontSize: 18, textAlignVertical: 'top' },
  composerFooter: { flexDirection: 'row', alignItems: 'center' },
  tool: { width: 40, height: 40, borderRadius: 20, backgroundColor: '#20232A', alignItems: 'center', justifyContent: 'center' },
  toolText: { color: '#F5F7FF', fontSize: 24, marginTop: -2 },
  modeHint: { color: '#747A87', fontSize: 11, marginLeft: 12, flex: 1 },
  send: { width: 42, height: 42, borderRadius: 21, backgroundColor: '#F5F7FF', alignItems: 'center', justifyContent: 'center' },
  sendDisabled: { opacity: 0.28 },
  sendText: { color: '#111216', fontSize: 25, fontWeight: '700', marginTop: -3 },
  resultCard: { marginTop: 18, borderRadius: 18, borderWidth: 1, borderColor: '#252932', backgroundColor: '#101217', padding: 16 },
  resultText: { color: '#E7E9EE', fontSize: 15, lineHeight: 22 },
  trace: { color: '#69707D', fontSize: 10, marginTop: 12 },
  quickGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginTop: 22 },
  quickCard: { width: '48%', paddingVertical: 18, paddingHorizontal: 16, borderRadius: 18, backgroundColor: '#111318', borderWidth: 1, borderColor: '#22252B' },
  quickText: { color: '#C7CBD3', fontSize: 14, fontWeight: '500' },
});
