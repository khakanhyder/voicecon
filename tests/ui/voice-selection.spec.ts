import type { Page } from '@playwright/test'
import { test, expect } from '../support/mocks'
import { enterDashboard } from '../support/session'
import { ROUTES } from '../support/routes'
import { AGENT_ID, agentDetail } from '../support/data'

/**
 * Voice Selection: previewing voices and the custom voice library.
 *
 * Previews are real audio played by the browser, so the stub answers with a
 * short silent WAV rather than JSON.
 */

const RACHEL = '21m00Tcm4TlvDq8ikWAM'
const DOMI = 'AZnzlk1XvdvUeBnXmlld'
const CLONE = 'AbCdEfGhIjKlMnOpQrSt'
const SECRET = 'sk_customer_secret_key'

const VOICES = /\/api\/v1\/voices(?:\?.*)?$/
const PREVIEW = /\/api\/v1\/voices\/preview$/
const CHECK = /\/api\/v1\/voices\/custom\/check$/
const CUSTOM = /\/api\/v1\/voices\/custom$/
const CUSTOM_ONE = /\/api\/v1\/voices\/custom\/[0-9a-f-]+$/

const PROVIDERS = [{
  slug: 'elevenlabs',
  label: 'ElevenLabs',
  fields: [
    { key: 'voice_id', label: 'Voice ID', required: true, secret: false, placeholder: '', help: '' },
    { key: 'api_key', label: 'ElevenLabs API key', required: false, secret: true, placeholder: '', help: '' },
  ],
}]

const SAVED_CLONE = {
  id: '00000000-0000-4000-8000-00000000c001',
  provider: 'elevenlabs',
  voice_id: CLONE,
  name: 'My Clone',
  category: 'cloned',
  description: null,
  labels: { accent: 'british' },
  uses_own_key: true,
  created_at: '2026-09-28T10:00:00Z',
}

/** A few seconds of silence: long enough to still be playing when asserted on. */
function silentWav(seconds = 4): Buffer {
  const rate = 8000
  const samples = rate * seconds
  const header = Buffer.alloc(44)
  header.write('RIFF', 0)
  header.writeUInt32LE(36 + samples, 4)
  header.write('WAVEfmt ', 8)
  header.writeUInt32LE(16, 16)
  header.writeUInt16LE(1, 20)
  header.writeUInt16LE(1, 22)
  header.writeUInt32LE(rate, 24)
  header.writeUInt32LE(rate, 28)
  header.writeUInt16LE(1, 32)
  header.writeUInt16LE(8, 34)
  header.write('data', 36)
  header.writeUInt32LE(samples, 40)
  return Buffer.concat([header, Buffer.alloc(samples, 128)])
}

/** Stubs the preview endpoint and returns the voice refs it was asked for. */
/** Requests that saved a custom voice (not the ones that only checked it). */
const savedVoices = (api: any) =>
  api.callsOf('POST', '/api/v1/voices/custom').filter((c: { url: string }) => CUSTOM.test(c.url))

async function stubPreview(page: Page) {
  const asked: Array<Record<string, string>> = []
  await page.route(PREVIEW, async (route) => {
    asked.push(route.request().postDataJSON())
    await route.fulfill({ status: 200, contentType: 'audio/wav', body: silentWav() })
  })
  return asked
}

async function openVoiceTab(page: Page, api: any, voiceId = RACHEL, custom: unknown[] = []) {
  await api.on(ROUTES.agent, {
    body: agentDetail({ tts_provider: 'elevenlabs', tts_voice_id: voiceId }),
  })
  await api.on(ROUTES.agentKnowledgeBases, { body: [] })
  await api.on(VOICES, { body: { providers: PROVIDERS, custom_voices: custom } })
  await enterDashboard(page, api, `/dashboard/agents/${AGENT_ID}`)
  await page.getByRole('button', { name: 'Voice Selection' }).first().click()
  await expect(page.getByRole('heading', { name: /Built-in Voices/ })).toBeVisible()
}

test.describe('Voice Selection', () => {
  test('plays one preview at a time and shows what each is doing', async ({ page, api }) => {
    const asked = await stubPreview(page)
    await openVoiceTab(page, api)

    await page.getByRole('button', { name: 'Play Rachel' }).click()
    await expect(page.getByRole('button', { name: 'Pause Rachel' })).toBeVisible()

    // Starting another voice stops the first.
    await page.getByRole('button', { name: 'Play Domi' }).click()
    await expect(page.getByRole('button', { name: 'Pause Domi' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Play Rachel' })).toBeVisible()
    await expect(page.getByRole('button', { name: /^Pause / })).toHaveCount(1)

    await page.getByRole('button', { name: 'Pause Domi' }).click()
    await expect(page.getByRole('button', { name: /^Pause / })).toHaveCount(0)

    // A voice already heard is replayed from memory, not fetched again.
    await page.getByRole('button', { name: 'Play Rachel' }).click()
    await expect(page.getByRole('button', { name: 'Pause Rachel' })).toBeVisible()
    expect(asked.map(a => a.voice_id)).toEqual([RACHEL, DOMI])
  })

  test('shows a loading state until the sample arrives', async ({ page, api }) => {
    let release: () => void = () => {}
    const held = new Promise<void>(resolve => { release = resolve })
    await page.route(PREVIEW, async (route) => {
      await held
      await route.fulfill({ status: 200, contentType: 'audio/wav', body: silentWav() })
    })
    await openVoiceTab(page, api)

    await page.getByRole('button', { name: 'Play Bella' }).click()
    await expect(page.getByRole('button', { name: 'Loading Bella' })).toBeVisible()
    release()
    await expect(page.getByRole('button', { name: 'Pause Bella' })).toBeVisible()
  })

  test('says why a voice could not be played', async ({ page, api }) => {
    await page.route(PREVIEW, route => route.fulfill({
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({ detail: "We couldn't find that voice. Check the Voice ID." }),
    }))
    await openVoiceTab(page, api)

    await page.getByRole('button', { name: 'Play Rachel' }).click()
    await expect(page.getByText("We couldn't find that voice")).toBeVisible()
    await expect(page.getByRole('button', { name: 'Play Rachel' })).toBeVisible()
  })

  test('previewing does not change the assistant; selecting and saving does', async ({ page, api }) => {
    await stubPreview(page)
    await openVoiceTab(page, api)

    await page.getByRole('button', { name: 'Play Domi' }).click()
    await expect(page.getByRole('button', { name: 'Pause Domi' })).toBeVisible()
    expect(api.callsOf('PATCH', `/api/v1/agents/${AGENT_ID}`)).toHaveLength(0)

    await page.getByRole('button', { name: 'Domi', exact: false }).filter({ hasText: 'Female' }).click()
    await page.getByRole('button', { name: 'Save Changes' }).click()
    await expect(page.getByText('Agent updated')).toBeVisible()

    const [patched] = api.callsOf('PATCH', `/api/v1/agents/${AGENT_ID}`)
    expect(patched.body).toMatchObject({ voice: { provider: 'elevenlabs', voice_id: DOMI } })
  })

  test('adds a custom voice after checking and hearing it', async ({ page, api }) => {
    const asked = await stubPreview(page)
    await api.on(CHECK, {
      body: { provider: 'elevenlabs', voice_id: CLONE, name: 'My Clone', category: 'cloned', description: null, labels: {} },
    })
    await api.on(CUSTOM, { status: 201, body: SAVED_CLONE }, { method: 'POST' })
    await openVoiceTab(page, api)

    await expect(page.getByText('No custom voices yet')).toBeVisible()
    await page.getByRole('button', { name: 'Add Custom Voice' }).click()
    const dialog = page.getByRole('dialog')

    // Nothing can be saved before the voice has been checked.
    await expect(dialog.getByRole('button', { name: 'Save voice' })).toHaveCount(0)
    await expect(dialog.getByRole('button', { name: 'Check voice' })).toBeDisabled()

    await dialog.getByLabel(/Voice ID/).fill(CLONE)
    await dialog.getByLabel(/API key/).fill(SECRET)
    await expect(dialog.getByLabel(/API key/)).toHaveAttribute('type', 'password')
    await dialog.getByRole('button', { name: 'Check voice' }).click()

    await expect(dialog.getByText('Voice found')).toBeVisible()
    await expect(dialog.getByLabel(/^Name/)).toHaveValue('My Clone')

    await dialog.getByRole('button', { name: 'Play My Clone' }).click()
    await expect(dialog.getByRole('button', { name: 'Pause My Clone' })).toBeVisible()
    expect(asked.at(-1)).toEqual({ provider: 'elevenlabs', voice_id: CLONE, api_key: SECRET })

    await dialog.getByRole('button', { name: 'Save voice' }).click()
    await expect(dialog).toBeHidden()

    // It joins the library, marked as custom, and becomes the selected voice.
    const card = page.getByRole('button', { name: /My Clone/ }).filter({ hasText: 'Custom' })
    await expect(card).toHaveAttribute('aria-pressed', 'true')
    const [saved] = savedVoices(api)
    expect(saved.body).toMatchObject({ voice_id: CLONE, api_key: SECRET, name: 'My Clone' })
    await expect(page.locator('body')).not.toContainText(SECRET)
  })

  test('a changed Voice ID must be checked again', async ({ page, api }) => {
    await api.on(CHECK, {
      body: { provider: 'elevenlabs', voice_id: CLONE, name: 'My Clone', category: 'cloned', description: null, labels: {} },
    })
    await openVoiceTab(page, api)
    await page.getByRole('button', { name: 'Add Custom Voice' }).click()
    const dialog = page.getByRole('dialog')

    await dialog.getByLabel(/Voice ID/).fill(CLONE)
    await dialog.getByRole('button', { name: 'Check voice' }).click()
    await expect(dialog.getByRole('button', { name: 'Save voice' })).toBeVisible()

    await dialog.getByLabel(/Voice ID/).fill(`${CLONE}x`)
    await expect(dialog.getByRole('button', { name: 'Save voice' })).toHaveCount(0)
    await expect(dialog.getByRole('button', { name: 'Check voice' })).toBeVisible()
  })

  test('explains a voice that could not be found and saves nothing', async ({ page, api }) => {
    await api.on(CHECK, {
      status: 404,
      body: { detail: "We couldn't find that voice. Check the Voice ID." },
    })
    await openVoiceTab(page, api)
    await page.getByRole('button', { name: 'Add Custom Voice' }).click()
    const dialog = page.getByRole('dialog')

    await dialog.getByLabel(/Voice ID/).fill(CLONE)
    await dialog.getByRole('button', { name: 'Check voice' }).click()

    await expect(dialog.getByRole('alert')).toContainText("We couldn't find that voice")
    await expect(dialog.getByRole('button', { name: 'Save voice' })).toHaveCount(0)
    expect(savedVoices(api)).toHaveLength(0)
  })

  test('an assistant using a custom voice opens with it selected', async ({ page, api }) => {
    await stubPreview(page)
    await openVoiceTab(page, api, CLONE, [SAVED_CLONE])

    const card = page.getByRole('button', { name: /My Clone/ }).filter({ hasText: 'Custom' })
    await expect(card).toHaveAttribute('aria-pressed', 'true')
    await expect(page.getByRole('heading', { name: /My Custom Voices/ })).toBeVisible()

    // Saving something unrelated must not swap the voice for a built-in one.
    await page.getByPlaceholder('e.g. Riley').fill('Riley v2')
    await page.getByRole('button', { name: 'Save Changes' }).click()
    await expect(page.getByText('Agent updated')).toBeVisible()
    const [patched] = api.callsOf('PATCH', `/api/v1/agents/${AGENT_ID}`)
    expect(patched.body).toMatchObject({ voice: { voice_id: CLONE } })
  })

  test('a voice still in use stays in the library when removal is refused', async ({ page, api }) => {
    await api.on(CUSTOM_ONE, {
      status: 409,
      body: { detail: 'This voice is used by: Riley. Choose another voice for those assistants first.' },
    }, { method: 'DELETE' })
    await openVoiceTab(page, api, RACHEL, [SAVED_CLONE])

    await page.getByRole('button', { name: 'Remove My Clone' }).click()
    await page.getByRole('button', { name: 'Remove', exact: true }).click()

    await expect(page.getByText('This voice is used by: Riley')).toBeVisible()
    await expect(page.getByRole('button', { name: /My Clone/ }).filter({ hasText: 'Custom' })).toBeVisible()
  })
})
