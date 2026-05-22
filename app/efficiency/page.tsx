import { Header } from '@/components/layout/Header';
import { EfficiencyBoard } from './efficiency-board';
import { loadPayload } from '@/lib/payload';

export default function EfficiencyPage() {
  const payload = loadPayload();
  return (
    <>
      <Header generatedAt={payload.meta.generated_at} active="efficiency" />
      <EfficiencyBoard payload={payload} />
    </>
  );
}
