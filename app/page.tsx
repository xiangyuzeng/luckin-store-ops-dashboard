import { Header } from '@/components/layout/Header';
import { DataInfoStrip } from '@/components/layout/DataInfoStrip';
import { HomeBoard } from './home-board';
import { loadPayload } from '@/lib/payload';

export default function HomePage() {
  const payload = loadPayload();
  return (
    <>
      <Header generatedAt={payload.meta.generated_at} active="home" />
      <DataInfoStrip meta={payload.meta} />
      <HomeBoard payload={payload} />
    </>
  );
}
