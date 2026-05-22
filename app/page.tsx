import { Header } from '@/components/layout/Header';
import { HomeBoard } from './home-board';
import { loadPayload } from '@/lib/payload';

export default function HomePage() {
  const payload = loadPayload();
  return (
    <>
      <Header generatedAt={payload.meta.generated_at} active="home" />
      <HomeBoard payload={payload} />
    </>
  );
}
