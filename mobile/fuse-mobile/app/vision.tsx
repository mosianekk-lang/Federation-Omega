import { useEffect, useState } from 'react';
import { Image, SafeAreaView, StyleSheet, Text, View } from 'react-native';
import { getOwnerVisionContext, getOwnerVisionImageSource } from '../src/ownerConnection';
import type { VisionContext } from '../src/federation';

type ImageSource = { uri: string; headers: Record<string, string> };

export default function VisionRoute() {
  const [ctx, setCtx] = useState<VisionContext | null>(null);
  const [image, setImage] = useState<ImageSource | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    const tick = async () => {
      try {
        const next = await getOwnerVisionContext();
        const nextImage = next.available ? await getOwnerVisionImageSource() : null;
        if (!active) return;
        setCtx(next);
        setImage(nextImage);
        setError('');
      } catch (failure) {
        if (active) setError(failure instanceof Error ? failure.message : 'VISION_CONTEXT_FAILED');
      }
    };
    void tick();
    const timer = setInterval(() => void tick(), 2000);
    return () => { active = false; clearInterval(timer); };
  }, []);

  return (
    <SafeAreaView style={styles.safe}><View style={styles.shell}>
      <Text style={styles.eyebrow}>FUSE VISION</Text>
      <Text style={styles.title}>Owner-view observation</Text>
      <Text style={styles.meta}>{error || (ctx?.available ? `${ctx.fresh ? 'fresh' : 'stale'} · ${ctx.sha256 ?? 'hash pending'}` : 'no accepted frame')}</Text>
      {ctx?.available && image ? <Image source={image} resizeMode="contain" style={styles.image} /> : <View style={styles.placeholder}><Text style={styles.placeholderText}>No accepted frame</Text></View>}
      <Text style={styles.boundary}>Observation is ephemeral and does not grant pointer, keyboard, provider, source or external-effect authority.</Text>
    </View></SafeAreaView>
  );
}

const styles=StyleSheet.create({safe:{flex:1,backgroundColor:'#090A0C'},shell:{flex:1,padding:20},eyebrow:{color:'#7F8795',fontSize:11,fontWeight:'800',letterSpacing:1.2},title:{color:'#F5F7FF',fontSize:30,fontWeight:'600',marginTop:14},meta:{color:'#9AA2AF',marginTop:10},image:{flex:1,marginTop:18,borderRadius:18,backgroundColor:'#111318'},placeholder:{flex:1,marginTop:18,borderRadius:18,borderWidth:1,borderColor:'#252A34',alignItems:'center',justifyContent:'center'},placeholderText:{color:'#707887'},boundary:{color:'#737B88',fontSize:11,lineHeight:16,marginTop:14}});
