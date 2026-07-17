// ============================================================================
//  PRUEBA DE CARGA REAL DEL BACKEND (k6)  —  Snake IA / FastAPI
// ============================================================================
//  Mide los endpoints REST autoritativos bajo concurrencia sostenida.
//  NO inventa numeros: k6 los mide contra el servidor corriendo de verdad.
//
//  1) Levanta el backend:        python ai_server.py         (puerto 8000)
//  2) Instala k6:                https://k6.io/docs/get-started/installation/
//                                (Windows: `winget install k6` o `choco install k6`)
//  3) Corre la prueba:           k6 run benchmarks/load_test.js
//
//  Los umbrales de abajo hacen que k6 marque PASS/FAIL: si el p95 supera 200ms
//  o la tasa de error pasa de 1%, la prueba falla. Asi el numero es honesto.
// ============================================================================
import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE = __ENV.BASE_URL || 'http://localhost:8000';

export const options = {
  scenarios: {
    carga_sostenida: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '15s', target: 50 },   // rampa de subida a 50 usuarios
        { duration: '30s', target: 50 },   // meseta: mide RPS/latencia estables
        { duration: '10s', target: 0 },    // bajada
      ],
    },
  },
  thresholds: {
    http_req_failed:   ['rate<0.01'],                 // Success Rate > 99%
    http_req_duration: ['p(95)<200', 'p(99)<500'],    // p95 < 200ms, p99 < 500ms
  },
};

export default function () {
  // Endpoints de solo lectura, seguros para golpear en bucle.
  const config = http.get(`${BASE}/api/config`);
  check(config, {
    'config 200': (r) => r.status === 200,
    'config trae limites': (r) => r.json('limits') !== undefined,
  });

  const models = http.get(`${BASE}/api/models`);
  check(models, { 'models 200': (r) => r.status === 200 });

  sleep(0.1);
}
