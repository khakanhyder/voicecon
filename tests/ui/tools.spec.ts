import { test, expect } from '../support/mocks'
import { enterDashboard } from '../support/session'
import { ROUTES } from '../support/routes'

/**
 * Tool rows put the name, a status pill and three actions on one line. They also
 * sit in a two-column grid from `xl` up, so a card there is roughly a third of
 * the viewport — the row has to give way on card width, not viewport width. It
 * used to key off `md:`, which collapsed the name to nothing and slid the pill
 * under the buttons on exactly the widest screens.
 */

const TOOLS = [
  { id: 't1', name: 'end_call', description: 'Ends the call', tool_type: 'hang_up',
    category: 'phone_call', is_active: true, config: {} },
  { id: 't2', name: 'transfer_to_human_agent', description: 'Transfers the caller',
    tool_type: 'transfer_call', category: 'phone_call', is_active: true, config: {} },
  { id: 't3', name: 'book_appointment_workflow', description: 'Books an appointment',
    tool_type: 'workflow', category: 'assistant', is_active: false, config: {} },
]

/** Widths that bracket every layout change, including the 2-column grid at xl. */
const WIDTHS: [string, number][] = [
  ['mobile', 390],
  ['tablet', 820],
  ['laptop', 1180],
  ['desktop', 1280],
  ['wide', 1920],
]

for (const [label, width] of WIDTHS) {
  test(`tool rows stay readable and clear of the actions on ${label}`, async ({ page, api }) => {
    await page.setViewportSize({ width, height: 900 })
    await api.on(ROUTES.tools, { body: { tools: TOOLS, total: TOOLS.length } })
    await enterDashboard(page, api, '/dashboard/tools')

    const name = page.getByRole('heading', { name: 'transfer_to_human_agent' })
    await name.waitFor()

    // A truncated-to-zero name is the symptom the old breakpoint produced.
    const nameBox = (await name.boundingBox())!
    expect(nameBox.width).toBeGreaterThan(20)

    // The name must not sit on top of the first action button.
    const btnBox = (await page.getByRole('button', { name: 'Test' }).nth(1).boundingBox())!
    const overlaps =
      nameBox.x + nameBox.width > btnBox.x + 1 &&
      nameBox.y + nameBox.height > btnBox.y + 1 &&
      btnBox.y + btnBox.height > nameBox.y + 1
    expect(overlaps).toBe(false)

    // Wrapping, not overflow — the page itself must never scroll sideways.
    const scrollsSideways = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
    )
    expect(scrollsSideways).toBe(false)
  })
}
