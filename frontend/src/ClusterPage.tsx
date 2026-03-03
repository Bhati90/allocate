// ClusterPage.tsx
import { useParams, useNavigate } from 'react-router-dom';
import { useState } from 'react';
import FarmScheduler from './Farm';
import Dialpad from './call';
import { Phone } from 'lucide-react';

const ClusterPage: React.FC = () => {
  const [dialpadOpen, setDialpadOpen] = useState(false);
  const [dialpadNumber, setDialpadNumber] = useState('');

  const { clusterId } = useParams<{ clusterId: string }>();
  const navigate = useNavigate();
  if (!clusterId) return null;

  return (
    <>
      <FarmScheduler
        clusterId={Number(clusterId)}
        onBackToClusters={() => navigate('/tender')}
        onOpenDialpadWithNumber={(phone: string) => {
          setDialpadNumber(phone || '');
          setDialpadOpen(true);
        }}
      />

      {/* global simple dialpad button (empty) */}
      <button
        type="button"
        onClick={() => {
          setDialpadNumber('');
          setDialpadOpen(true);
        }}
        className="fixed bottom-6 right-6 bg-green-500 hover:bg-green-600 text-white rounded-full p-4 shadow-lg transition-all hover:scale-110 z-40"
      >
        <Phone className="w-6 h-6" />
      </button>

      <Dialpad
        isOpen={dialpadOpen}
        number={dialpadNumber}
        onClose={() => setDialpadOpen(false)}
        onNumberChange={setDialpadNumber}
      />
    </>
  );
};

export default ClusterPage;
