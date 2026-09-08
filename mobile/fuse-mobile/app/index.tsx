import { useMemo, useState } from 'react';
import { Pressable, SafeAreaView, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

type Mode = 'AUTO' | 'THINK' | 'CREATE' | 'BUILD' | 'RESEARCH';
const modes: Mode[] = ['AUTO', 'THINK', 'CREATE', 'BUILD', 'RESEARCH'];

export default function Home() {
  const [mode, setMode] = useState<Mode>('AUTO');
  const [text, setText] = useState('');
  const canSend = useMemo(() => text.trim().length > 0, [text]);

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.shell}>
        <View style={styles.brandRow}>
          <View style={styles.pulse} />
          <Text style={styles.brand}>FUSE</Text>
          <Text style={styles.owner}>Ω</Text>
        </View>
        <Text style={styles.hero}>What are we building today?</Text>

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
            <Pressable disabled={!canSend} style={[styles.send, !canSend && styles.sendDisabled]}>
              <Text style={styles.sendText}>↑</Text>
            </Pressable>
          </View>
        </View>

        <View style={styles.quickGrid}>
          {['Federation', 'Creative', 'Research', 'Workspace'].map((label) => (
            <Pressable key={label} style={styles.quickCard}><Text style={styles.quickText}>{label}</Text></Pressable>
          ))}
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#090A0C' },
  shell: { flex: 1, paddingHorizontal: 20, paddingTop: 24 },
  brandRow: { flexDirection: 'row', alignItems: 'center', gap: 9 },
  pulse: { width: 12, height: 12, borderRadius: 6, backgroundColor: '#F5F7FF' },
  brand: { color: '#F5F7FF', fontSize: 20, fontWeight: '700', letterSpacing: 3 },
  owner: { color: '#8D93A1', fontSize: 16 },
  hero: { color: '#F5F7FF', fontSize: 34, lineHeight: 41, fontWeight: '600', marginTop: 74, maxWidth: 330 },
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
  quickGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginTop: 22 },
  quickCard: { width: '48%', paddingVertical: 18, paddingHorizontal: 16, borderRadius: 18, backgroundColor: '#111318', borderWidth: 1, borderColor: '#22252B' },
  quickText: { color: '#C7CBD3', fontSize: 14, fontWeight: '500' },
});
