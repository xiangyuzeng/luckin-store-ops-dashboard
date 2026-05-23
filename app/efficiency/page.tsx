import { Header } from '@/components/layout/Header';
import { DataInfoStrip } from '@/components/layout/DataInfoStrip';
import { EfficiencyBoard } from './efficiency-board';
import { loadPayload } from '@/lib/payload';

export default function EfficiencyPage() {
  const payload = loadPayload();
  return (
    <>
      <Header generatedAt={payload.meta.generated_at} active="efficiency" />
      <DataInfoStrip meta={payload.meta} />
      <EfficiencyBoard payload={payload} />
    </>
  );
}
