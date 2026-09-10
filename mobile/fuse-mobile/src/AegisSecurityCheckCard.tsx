import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { runOwnerTriggeredAegisSecurityCheck } from './aegisSecurityCheck';

type CheckState = 'IDLE' | 'RUNNING' | 'COMPLETE' | 'ERROR';

export function AegisSecurityCheckCard() {
  const [state, setState] = useState<CheckState>('IDLE');
  const [message, setMessage] = useState('No background monitoring. Run only when you choose.');
  const [trace, setTrace] = useState<string | null>(null);

  async function runCheck() {
    if (state === 'RUNNING') return;
    setState('RUNNING');
    setMessage('Checking coarse device security posture…');
    setTrace(null);
    try {
      const receipt = await runOwnerTriggeredAegisSecurityCheck();
      setState('COMPLETE');
      setMessage(receipt.event_count > 0
        ? `AEGIS completed: ${receipt.status}. ${receipt.event_count} security signal(s) submitted.`
        : 'AEGIS completed: no risk signals were emitted from the available posture fields.');
      setTrace(receipt.case_id
        ? `Case ${receipt.case_id.slice(0, 16)} · Request ${receipt.request_id.slice(0, 12)}`
        : `Request ${receipt.request_id.slice(0, 16)}`);
    } catch (error) {
      setState('ERROR');
      setMessage(error instanceof Error ? error.message : 'AEGIS_SECURITY_CHECK_FAILED');
    }
  }

  return (
    <View style={styles.card} accessibilityLabel="AEGIS security check">
      <Text style={styles.title}>AEGIS security check</Text>
      <Text style={styles.copy}>{message}</Text>
      <Text style={styles.privacy}>
        Shares only coarse, consent-bound posture. No contacts, messages, location, device identifiers or app inventory.
      </Text>
      <Pressable
        accessibilityRole="button"
        onPress={runCheck}
        disabled={state === 'RUNNING'}
        style={[styles.button, state === 'RUNNING' && styles.disabled]}
      >
        <Text style={styles.buttonText}>{state === 'RUNNING' ? 'Checking…' : 'Run AEGIS security check'}</Text>
      </Pressable>
      {trace ? <Text style={styles.trace}>{trace}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: { marginTop: 18, borderRadius: 18, borderWidth: 1, borderColor: '#252932', backgroundColor: '#101217', padding: 16 },
  title: { color: '#F5F7FF', fontSize: 15, fontWeight: '700' },
  copy: { color: '#C7CBD3', fontSize: 13, lineHeight: 19, marginTop: 7 },
  privacy: { color: '#7F8795', fontSize: 11, lineHeight: 16, marginTop: 10 },
  button: { alignSelf: 'flex-start', marginTop: 14, borderRadius: 18, backgroundColor: '#F5F7FF', paddingHorizontal: 15, paddingVertical: 10 },
  disabled: { opacity: 0.45 },
  buttonText: { color: '#111216', fontSize: 12, fontWeight: '700' },
  trace: { color: '#69707D', fontSize: 10, marginTop: 10 },
});
