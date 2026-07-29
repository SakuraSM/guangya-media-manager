import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { StatusBadge } from './StatusBadge'

describe('StatusBadge', () => {
  it('renders textual status in addition to color', () => {
    render(<StatusBadge status="REVIEW_REQUIRED" />)

    expect(screen.getByText('等待审核')).toBeVisible()
  })
})
