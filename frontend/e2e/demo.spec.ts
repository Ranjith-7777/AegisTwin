import { expect, type APIRequestContext, type Page, test } from '@playwright/test'

const api = 'http://127.0.0.1:8010/api/v1'

async function prepare(request: APIRequestContext) {
  const topologyBefore = await (
    await request.get(`${api}/topology?include_synthetic_sink=true`)
  ).json()
  const model = await (
    await request.post(`${api}/detection/models/train`, {
      data: {
        training_seed_range: { start: 1, end: 5 },
        validation_seed_range: { start: 6, end: 10 },
        evaluation_seed_range: { start: 11, end: 13 },
        random_state: 17,
        target_false_positive_rate: 0.1,
        n_estimators: 100,
      },
    })
  ).json()
  const run = await (
    await request.post(`${api}/simulation/runs`, {
      data: {
        scenario_id: 'staged-compromise-demo',
        seed: 84,
        start_time: '2026-07-21T01:30:00Z',
        playback_speed: 50,
      },
    })
  ).json()
  expect(
    (
      await request.post(`${api}/detection/runs/${run.simulation_run_id}/score`, {
        data: { model_id: model.model_id },
      })
    ).ok(),
  ).toBeTruthy()
  const correlation = await (
    await request.post(`${api}/correlation/runs/${run.simulation_run_id}/analyze`, {
      data: { model_id: model.model_id },
    })
  ).json()
  const prediction = await (
    await request.post(`${api}/prediction/runs/${run.simulation_run_id}/analyze`, {
      data: { model_id: model.model_id, top_k: 3 },
    })
  ).json()
  const response = await (
    await request.post(`${api}/response/runs/${run.simulation_run_id}/analyze`, {
      data: {
        model_id: model.model_id,
        through_sequence_number: 10,
        prediction_enabled: true,
        top_k: 10,
      },
    })
  ).json()
  return { run, model, correlation, prediction, response, topologyBefore }
}

async function expectSafety(page: Page) {
  await expect(
    page.getByRole('status', { name: 'Simulation environment safety notice' }),
  ).toBeVisible()
}

test('complete deterministic synthetic demonstration workflow', async ({ page, request }) => {
  const consoleErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  const prepared = await prepare(request)
  expect(prepared.prediction.snapshot_count).toBe(12)
  expect(prepared.correlation.synthetic).toBe(true)
  const recommendation = prepared.response.recommendations.find(
    (item: { required_approval_tier: string; simulation: { reversibility: string } }) =>
      item.required_approval_tier === 'analyst_approval' &&
      item.simulation.reversibility === 'reversible',
  )
  expect(recommendation).toBeTruthy()
  const orchestration = await (
    await request.post(`${api}/orchestration/runs/${prepared.run.simulation_run_id}/create`, {
      data: {
        model_id: prepared.model.model_id,
        incident_candidate_id: recommendation.incident_candidate_id,
        selected_recommendation_id: recommendation.recommendation_id,
        through_sequence_number: 10,
      },
    })
  ).json()
  expect(orchestration.current_state).toBe('awaiting_analyst_approval')
  const approval = orchestration.approvals[0]
  const approved = await (
    await request.post(
      `${api}/orchestration/${orchestration.orchestration_id}/approvals/${approval.approval_request_id}/decide`,
      {
        data: {
          actor_role: 'analyst',
          actor_display_name: 'Demo SOC Analyst',
          decision: 'approve',
          reason: 'Approved for deterministic synthetic demonstration only.',
        },
      },
    )
  ).json()
  expect(approved.current_state).toBe('approved')
  const executed = await (
    await request.post(`${api}/orchestration/${orchestration.orchestration_id}/execute`, {
      data: {},
    })
  ).json()
  expect(executed.executions[0].execution_state).toBe('completed_simulated')
  const verified = await (
    await request.post(`${api}/orchestration/${orchestration.orchestration_id}/verify`)
  ).json()
  expect(verified.verifications[0].verification_status).toBe('successful_simulation')
  const rolledBack = await (
    await request.post(`${api}/orchestration/${orchestration.orchestration_id}/rollback`, {
      data: {
        reason: 'Restore deterministic synthetic baseline.',
        requested_by: 'Demo SOC Analyst',
      },
    })
  ).json()
  expect(rolledBack.current_state).toBe('synthetic_rollback_completed')
  const integrity = await (
    await request.get(`${api}/orchestration/${orchestration.orchestration_id}/audit/verify`)
  ).json()
  expect(integrity.valid).toBe(true)
  const topologyAfter = await (
    await request.get(`${api}/topology?include_synthetic_sink=true`)
  ).json()
  expect(topologyAfter.nodes).toEqual(prepared.topologyBefore.nodes)
  expect(topologyAfter.edges).toEqual(prepared.topologyBefore.edges)

  await page.goto('/')
  await expectSafety(page)
  await expect(page.getByText(/Backend: Connected/i)).toBeVisible()
  await page.goto('/incidents')
  await expectSafety(page)
  await page.goto('/predictive-analytics')
  await expect(page.getByRole('heading', { name: /Predictive Analytics/i })).toBeVisible()
  await page.goto('/digital-twin')
  await expect(page.getByRole('heading', { name: /Cloud Digital Twin/i })).toBeVisible()
  await page.goto('/response-centre')
  await expect(page.getByRole('heading', { name: /Blue Agent/i })).toBeVisible()
  await page.goto('/response-operations')
  const orchestrationState = page.locator('p').filter({
    has: page.locator('strong').filter({ hasText: /^State:$/ }),
  })
  await expect(orchestrationState).toContainText('synthetic rollback completed')
  await expect(page.getByText(/Simulation agent workflow/i)).toBeVisible()
  await page.goto('/audit-trail')
  await page.getByRole('button', { name: 'Verify Audit Chain' }).click()
  await expect(page.getByText(/Chain integrity:/i)).toContainText('valid')
  expect(consoleErrors).toEqual([])
})

test('telemetry-only and detection-only records remain separated', async ({ request }) => {
  const normal = await (
    await request.post(`${api}/simulation/runs`, {
      data: {
        scenario_id: 'normal-operations',
        seed: 8,
        start_time: '2026-07-21T02:00:00Z',
        playback_speed: 50,
      },
    })
  ).json()
  const events = await (
    await request.get(`${api}/telemetry/events?simulation_run_id=${normal.simulation_run_id}`)
  ).json()
  expect(events.items.length).toBeGreaterThan(0)
  const incidents = await (
    await request.get(`${api}/correlation/runs/${normal.simulation_run_id}/incidents`)
  ).json()
  expect(incidents.total).toBe(0)
})

test('rejection, administrator enforcement, and deterministic failure remain gated', async ({
  request,
}) => {
  const prepared = await prepare(request)
  const administrator = prepared.response.recommendations.find(
    (item: { required_approval_tier: string }) =>
      item.required_approval_tier === 'administrator_approval',
  )
  expect(administrator).toBeTruthy()
  const orchestration = await (
    await request.post(`${api}/orchestration/runs/${prepared.run.simulation_run_id}/create`, {
      data: {
        model_id: prepared.model.model_id,
        incident_candidate_id: administrator.incident_candidate_id,
        selected_recommendation_id: administrator.recommendation_id,
        through_sequence_number: 10,
      },
    })
  ).json()
  const approval = orchestration.approvals[0]
  const analystAttempt = await request.post(
    `${api}/orchestration/${orchestration.orchestration_id}/approvals/${approval.approval_request_id}/decide`,
    {
      data: {
        actor_role: 'analyst',
        actor_display_name: 'Demo SOC Analyst',
        decision: 'approve',
        reason: 'Role boundary test.',
      },
    },
  )
  expect(analystAttempt.status()).toBe(403)
  const rejected = await request.post(
    `${api}/orchestration/${orchestration.orchestration_id}/approvals/${approval.approval_request_id}/decide`,
    {
      data: {
        actor_role: 'administrator',
        actor_display_name: 'Demo Security Administrator',
        decision: 'reject',
        reason: 'Synthetic rejection demonstration.',
      },
    },
  )
  expect(rejected.ok()).toBeTruthy()
  expect(
    (
      await request.post(`${api}/orchestration/${orchestration.orchestration_id}/execute`, {
        data: {},
      })
    ).status(),
  ).toBe(409)
})
