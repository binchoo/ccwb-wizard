# Claude Code on Bedrock — Architecture Diagrams (Vite + React + xyflow)

`@xyflow/react`로 그린 인터랙티브 아키텍처 다이어그램. 노드 드래그/줌/팬, MiniMap, 컨트롤 패널 모두 동작.

## 두 개의 다이어그램

1. **Admin · 배포 산출물 생성** (`AdminDeploymentDiagram`)
   IT Admin이 `ccwb` CLI로 AWS에 인증·빌드·관제 스택을 배포하고, 사용자 배포용 zip 산출물을 만들기까지의 흐름.
   인증(IAM OIDC), 빌드(CodeBuild), 관제는 Central(ECS+ALB+Analytics)/Sidecar(Dashboard만) 두 분기로 비교.

2. **User · Installer 로컬 구성** (`UserInstallerDiagram`)
   End User가 zip을 받아 `install.sh` 1회 실행으로 로컬을 구성한 뒤, 첫 `claude` 실행 시 OIDC → STS → Bedrock → 텔레메트리(OTLP) 체인이 작동하는 흐름.
   Quota check가 호출되는 3개 시점을 점선으로 강조.

상단 탭으로 두 다이어그램을 전환.

## 실행

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # 정적 빌드 → dist/
npm run preview  # 빌드 결과 로컬 프리뷰
```

## 디렉토리 구조

```
src/
├─ App.tsx                          # 헤더 + 탭 셸
├─ main.tsx                         # 엔트리
├─ styles.css                       # 노드/그룹/범례 스타일
├─ components/
│  ├─ AwsNode.tsx                   # 공통 노드 (title/subtitle/tag + 카테고리 색)
│  ├─ GroupNode.tsx                 # 그룹 컨테이너 (AWS Account, 로컬, 관제 등)
│  └─ Legend.tsx                    # 우하단 범례 패널
└─ diagrams/
   ├─ AdminDeploymentDiagram.tsx    # 다이어그램 1
   ├─ adminNodes.ts                 # 노드 정의
   ├─ adminEdges.ts                 # 엣지 정의 + 색상 코드
   ├─ UserInstallerDiagram.tsx      # 다이어그램 2
   ├─ userNodes.ts
   └─ userEdges.ts
```

## 다이어그램 수정하는 법

- **노드 추가/이동**: `*Nodes.ts`에서 `position`, `data` 수정
- **엣지 추가**: `*Edges.ts`의 헬퍼(`arrow`, `dashed`)와 색상 상수(`C`)를 활용
- **카테고리 색상 추가**: `styles.css`의 `.node-card.cat-*` 추가하고 `AwsNode` 타입에 등록
- **그룹 박스 변형**: `styles.css`의 `.group-node.group-*` 추가하고 `GroupNode` 타입에 등록

## 정적 검증

```bash
npx tsc -b      # 타입 체크
npm run build   # 풀 빌드 (tsc + Vite)
```

## 스크린샷

`_screenshots/` 폴더에 두 탭 스냅샷이 들어 있다 (gitignored).
