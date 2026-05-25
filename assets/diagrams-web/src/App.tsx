import { useState } from 'react';
import { AdminDeploymentDiagram } from './diagrams/AdminDeploymentDiagram';
import { UserInstallerDiagram } from './diagrams/UserInstallerDiagram';

type TabKey = 'admin' | 'user';

export default function App() {
  const [tab, setTab] = useState<TabKey>('admin');

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>Claude Code on Bedrock — Architecture</h1>
        <span className="subtitle">Vite + React + xyflow</span>
        <div className="tab-bar">
          <button
            className={`tab-btn ${tab === 'admin' ? 'active' : ''}`}
            onClick={() => setTab('admin')}
          >
            1. Admin · 배포 산출물 생성
          </button>
          <button
            className={`tab-btn ${tab === 'user' ? 'active' : ''}`}
            onClick={() => setTab('user')}
          >
            2. User · Installer 로컬 구성
          </button>
        </div>
      </header>
      <main className="diagram-container">
        {tab === 'admin' ? <AdminDeploymentDiagram /> : <UserInstallerDiagram />}
      </main>
    </div>
  );
}
