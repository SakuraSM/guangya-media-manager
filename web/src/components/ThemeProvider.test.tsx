import type { ReactNode } from 'react'
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

vi.mock('next-themes', () => ({
  ThemeProvider: ({
    children,
    defaultTheme,
    enableSystem,
    storageKey,
  }: {
    children: ReactNode
    defaultTheme?: string
    enableSystem?: boolean
    storageKey?: string
  }) => (
    <div
      data-testid="theme-provider"
      data-default-theme={defaultTheme}
      data-enable-system={String(enableSystem)}
      data-storage-key={storageKey}
    >
      {children}
    </div>
  ),
}))

import { ThemeProvider } from './ThemeProvider'

describe('ThemeProvider', () => {
  it('follows the system by default and persists manual choices', () => {
    render(
      <ThemeProvider>
        <span>应用内容</span>
      </ThemeProvider>,
    )

    const provider = screen.getByTestId('theme-provider')
    expect(provider).toHaveAttribute('data-default-theme', 'system')
    expect(provider).toHaveAttribute('data-enable-system', 'true')
    expect(provider).toHaveAttribute('data-storage-key', 'guangya-media-theme')
  })
})
