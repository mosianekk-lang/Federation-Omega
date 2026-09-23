import { useEffect, useState } from 'react';
import { SafeAreaView, ScrollView, StyleSheet, Text, View } from 'react-native';
import { getOwnerMarketResidualStatus } from '../src/ownerConnection';
import type { MarketResidualStatus } from '../src/federation';

export default function MarketRoute() {
  const [status, setStatus] = useState<MarketResidualStatus | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    getOwnerMarketResidualStatus()
      .then((next) => {
        if (!active) return;
        setStatus(next);
        setError('');
      })
      .catch((failure) => {
        if (active) setError(failure instanceof Error ? failure.message : 'MARKET_RESIDUAL_STATUS_FAILED');
      });
    return () => { active = false; };
  }, []);

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.shell}>
        <Text style={styles.eyebrow}>FUSE MARKET CONVERGENCE</Text>
        <Text style={styles.title}>Market-frontier residuals</Text>
        <Text style={styles.body}>
          These are control/projection capabilities over existing FUSE roots. They do not prove live browser,
          computer-use, restore, or market leadership.
        </Text>
        {error ? <Text style={styles.error}>{error}</Text> : null}
        <Text style={styles.meta}>Version: {status?.version ?? 'checking'}</Text>
        <Text style={styles.meta}>New state roots: {status?.state_roots_added ?? '—'}</Text>
        <Text style={styles.meta}>New authority roots: {status?.authority_roots_added ?? '—'}</Text>
        <View style={styles.card}>
          {(status?.capabilities ?? []).map((capability) => (
            <Text key={capability} style={styles.capability}>• {capability}</Text>
          ))}
        </View>
        <Text style={styles.boundary}>{status?.truth_boundary ?? 'Loading truth boundary…'}</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#090A0C' },
  shell: { padding: 24 },
  eyebrow: { color: '#7F8795', fontSize: 11, fontWeight: '800', letterSpacing: 1.3 },
  title: { color: '#F5F7FF', fontSize: 32, lineHeight: 38, fontWeight: '600', marginTop: 16 },
  body: { color: '#9AA2AF', fontSize: 15, lineHeight: 23, marginTop: 14 },
  error: { color: '#FF9B9B', marginTop: 18 },
  meta: { color: '#D7DCE5', fontSize: 13, marginTop: 14 },
  card: { marginTop: 20, padding: 18, borderRadius: 16, backgroundColor: '#111318' },
  capability: { color: '#D7DCE5', fontSize: 13, lineHeight: 22 },
  boundary: { color: '#737B88', fontSize: 11, lineHeight: 16, marginTop: 18 },
});
