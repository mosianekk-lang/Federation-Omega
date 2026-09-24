import { useEffect, useState } from 'react';
import { SafeAreaView, StyleSheet, Text, View } from 'react-native';
import { getOwnerWorkspaceStatus } from '../src/ownerConnection';

export default function WorkspaceRoute() {
  const [status, setStatus] = useState('checking');
  const [root, setRoot] = useState('—');

  useEffect(() => {
    let active = true;
    getOwnerWorkspaceStatus()
      .then((next) => {
        if (!active) return;
        setStatus('ready');
        setRoot(next.mission_state_root);
      })
      .catch((error) => active && setStatus(error instanceof Error ? error.message : 'WORKSPACE_STATUS_FAILED'));
    return () => { active = false; };
  }, []);

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.shell}>
        <Text style={styles.eyebrow}>FUSE WORKSPACE</Text>
        <Text style={styles.title}>Mission state lives outside chat.</Text>
        <Text style={styles.body}>This client reuses the existing FUSE Mobile Gateway and owner session. Mission Bus and Work Plane remain the durable state authority.</Text>
        <Text style={styles.status}>Workspace: {status}</Text>
        <Text style={styles.status}>State root: {root}</Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe:{flex:1,backgroundColor:'#090A0C'}, shell:{flex:1,padding:24}, eyebrow:{color:'#7F8795',fontSize:11,fontWeight:'800',letterSpacing:1.3},
  title:{color:'#F5F7FF',fontSize:34,lineHeight:40,fontWeight:'600',marginTop:18}, body:{color:'#9AA2AF',fontSize:16,lineHeight:24,marginTop:16}, status:{color:'#D7DCE5',fontSize:13,marginTop:20}
});
