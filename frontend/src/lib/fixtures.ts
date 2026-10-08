// Contract fixtures (Part A's agreed response shapes). Used whenever the engine API isn't up yet.
import alertsCleared from '../../../contracts/alerts_cleared.json';
import audit from '../../../contracts/audit.json';
import caseDetail from '../../../contracts/case_detail.json';
import caseGraph from '../../../contracts/case_graph.json';
import decision from '../../../contracts/decision.json';
import document from '../../../contracts/document.json';
import forecast from '../../../contracts/forecast.json';
import overview from '../../../contracts/overview.json';
import queue from '../../../contracts/queue.json';
import timemachine from '../../../contracts/timemachine.json';
import trust from '../../../contracts/trust.json';
import twinHarden from '../../../contracts/twin_harden.json';
import twinRun from '../../../contracts/twin_run.json';
import twinScenarios from '../../../contracts/twin_scenarios.json';

export const fixtures = {
  alertsCleared, audit, caseDetail, caseGraph, decision, document, forecast, overview, queue,
  timemachine, trust, twinHarden, twinRun, twinScenarios,
};

export const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
