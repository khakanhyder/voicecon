/**
 * The profile picture control.
 *
 * The client-side checks here are a courtesy — the server validates again and
 * is the only side that can be trusted — but they must reject the obvious
 * cases without a round-trip, and must never leave the UI showing a picture
 * that failed to save.
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, describe, expect, it, vi } from 'vitest'

import { AvatarUploader } from './avatar-uploader'

// jsdom implements neither, and the component uses them for the in-flight preview.
beforeAll(() => {
  URL.createObjectURL = vi.fn(() => 'blob:preview')
  URL.revokeObjectURL = vi.fn()
})

const png = (name = 'me.png', size = 1024) => {
  const file = new File(['x'], name, { type: 'image/png' })
  Object.defineProperty(file, 'size', { value: size })
  return file
}

function setup(props: Partial<React.ComponentProps<typeof AvatarUploader>> = {}) {
  const onUpload = vi.fn().mockResolvedValue(undefined)
  const onRemove = vi.fn().mockResolvedValue(undefined)
  render(
    <AvatarUploader
      src={null}
      name="Sajid Ali"
      onUpload={onUpload}
      onRemove={onRemove}
      {...props}
    />
  )
  return { onUpload, onRemove }
}

const fileInput = () => document.querySelector('input[type="file"]') as HTMLInputElement

describe('AvatarUploader', () => {
  it('falls back to the initial when there is no picture', () => {
    setup()
    expect(screen.getByText('S')).toBeInTheDocument()
  })

  it('uploads a chosen image', async () => {
    const user = userEvent.setup()
    const { onUpload } = setup()

    await user.upload(fileInput(), png())

    await waitFor(() => expect(onUpload).toHaveBeenCalledTimes(1))
    expect(onUpload.mock.calls[0][0].name).toBe('me.png')
  })

  it('rejects a file that is not an accepted image', async () => {
    const user = userEvent.setup()
    const { onUpload } = setup()

    await user.upload(fileInput(), new File(['x'], 'notes.pdf', { type: 'application/pdf' }))

    expect(await screen.findByText(/JPEG, PNG, WebP or GIF/i)).toBeInTheDocument()
    expect(onUpload).not.toHaveBeenCalled()
  })

  it('rejects a file over the size limit and says how big it was', async () => {
    const user = userEvent.setup()
    const { onUpload } = setup()

    await user.upload(fileInput(), png('huge.png', 6 * 1024 * 1024))

    expect(await screen.findByText(/6\.0MB.*limit is 5MB/i)).toBeInTheDocument()
    expect(onUpload).not.toHaveBeenCalled()
  })

  it('offers remove only when a picture exists', () => {
    const { unmount } = render(
      <AvatarUploader src={null} name="Sajid" onUpload={vi.fn()} onRemove={vi.fn()} />
    )
    expect(screen.queryByRole('button', { name: /remove/i })).not.toBeInTheDocument()
    unmount()

    setup({ src: 'https://cdn.example.com/a.png' })
    expect(screen.getByRole('button', { name: /remove/i })).toBeInTheDocument()
  })

  it('removes the picture when asked', async () => {
    const user = userEvent.setup()
    const { onRemove } = setup({ src: 'https://cdn.example.com/a.png' })

    await user.click(screen.getByRole('button', { name: /remove/i }))

    await waitFor(() => expect(onRemove).toHaveBeenCalled())
  })

  it('drops the optimistic preview when the upload fails', async () => {
    const user = userEvent.setup()
    const onUpload = vi.fn().mockRejectedValue(new Error('nope'))
    render(
      <AvatarUploader src={null} name="Sajid Ali" onUpload={onUpload} onRemove={vi.fn()} />
    )

    await user.upload(fileInput(), png())

    // Back to the placeholder — never claim a picture that was not stored.
    await waitFor(() => expect(screen.getByText('S')).toBeInTheDocument())
  })

  it('lets the same file be picked twice in a row', async () => {
    const user = userEvent.setup()
    const { onUpload } = setup()

    await user.upload(fileInput(), png())
    await waitFor(() => expect(onUpload).toHaveBeenCalledTimes(1))
    // Without clearing input.value the second pick fires no change event at all.
    await user.upload(fileInput(), png())

    await waitFor(() => expect(onUpload).toHaveBeenCalledTimes(2))
  })

  it('cannot be used while disabled', async () => {
    const user = userEvent.setup()
    const { onUpload } = setup({ src: 'https://cdn.example.com/a.png', disabled: true })

    expect(screen.getByRole('button', { name: /change picture/i })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: /change profile picture/i }))

    expect(onUpload).not.toHaveBeenCalled()
  })
})
