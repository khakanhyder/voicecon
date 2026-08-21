import { test, expect } from '../support/mocks'
import { enterDashboard } from '../support/session'
import { ROUTES } from '../support/routes'
import { agent, agentDetail, agentListResponse, AGENT_ID } from '../support/data'

/**
 * The agent editor is the widest screen in the product — a form column, a side
 * rail and a ten-item tab bar — and it is the one most often opened on a phone
 * between calls.
 *
 * The regression this guards: `main` in dashboard/layout.tsx scrolls on the Y
 * axis only, so anything wider than the column is *clipped*, not scrollable —
 * controls simply vanish off the right edge with no way to reach them. One long
 * unbreakable tool name was enough to stretch the auto-sized grid track and
 * push the Save button off screen, which is why a tool name with no spaces is
 * part of the fixture rather than a tidy "Book appointment".
 */
const TOOLS = [
  {
    id: 't1',
    name: 'book_solar_survey_for_the_caller',
    description: 'Books a survey',
    tool_type: 'workflow',
    category: 'assistant',
    is_active: true,
  },
  {
    id: 't2',
    name: 'estimate_solar_savings_from_a_postcode',
    description: 'Estimates savings',
    tool_type: 'api_request',
    category: 'integration',
    is_active: true,
  },
]

/** Phone, tablet, and the width where the side rail appears. */
const WIDTHS = [390, 768, 1280]
const TABS = ['Prompt', 'Voice Selection', 'Tools', 'Conversation']

test('the agent editor fits its column on every screen', async ({ page, api }) => {
  const name = 'Nova — BrightWatt Solar Advisor'
  await api.on(ROUTES.agent, { body: agentDetail({ name }) })
  await api.on(ROUTES.agents, { body: agentListResponse([agent({ name })]) })
  await api.on(ROUTES.agentKnowledgeBases, { body: [] })
  await api.on(ROUTES.agentTools, {
    body: [{ id: 'a1', agent_id: AGENT_ID, tool_id: 't1', tool: TOOLS[0], created_at: '2026-01-01T00:00:00Z' }],
  })
  await api.on(ROUTES.tools, { body: { tools: TOOLS, total: TOOLS.length } })
  await api.on(ROUTES.knowledgeBases, { body: [] })
  await api.on(ROUTES.workflows, { body: { workflows: [] } })

  await enterDashboard(page, api, `/dashboard/agents/${AGENT_ID}`)
  await expect(page.getByRole('heading', { name: 'Assistant', exact: true })).toBeVisible()

  const overflowing: string[] = []
  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: 1000 })
    for (const tab of TABS) {
      await page.getByRole('button', { name: tab, exact: true }).click()
      // The tab bar itself is a horizontal scroller by design, so measure the
      // page container instead of the document.
      const { scrollWidth, clientWidth } = await page.evaluate(() => {
        const main = document.querySelector('main') as HTMLElement
        return { scrollWidth: main.scrollWidth, clientWidth: main.clientWidth }
      })
      if (scrollWidth > clientWidth + 1) {
        overflowing.push(`${width}px / ${tab}: content ${scrollWidth}px in a ${clientWidth}px column`)
      }
    }
  }

  expect(overflowing).toEqual([])
})
