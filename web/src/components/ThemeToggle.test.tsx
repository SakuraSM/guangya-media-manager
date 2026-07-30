import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

const { setTheme } = vi.hoisted(() => ({ setTheme: vi.fn() }))

vi.mock('next-themes', () => ({
  useTheme: () => ({
    theme: 'system',
    setTheme,
  }),
}))

import { ThemeToggle } from './ThemeToggle'

describe('ThemeToggle', () => {
  it('offers light, dark, and system themes', () => {
    render(<ThemeToggle />)

    fireEvent.keyDown(
      screen.getByRole('button', { name: '切换界面主题' }),
      { key: 'Enter' },
    )

    expect(screen.getByRole('menuitem', { name: '浅色' })).toBeVisible()
    expect(screen.getByRole('menuitem', { name: '深色' })).toBeVisible()
    expect(screen.getByRole('menuitem', { name: /跟随系统/ })).toBeVisible()

    fireEvent.click(screen.getByRole('menuitem', { name: '深色' }))
    expect(setTheme).toHaveBeenCalledWith('dark')
  })
})
