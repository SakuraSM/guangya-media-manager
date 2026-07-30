import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { BrandLogo } from './BrandLogo'

describe('BrandLogo', () => {
  it('uses the canonical public logo asset', () => {
    const { container } = render(<BrandLogo size="login" />)
    const logo = container.querySelector('img')

    expect(logo).toHaveAttribute('src', '/logo.png')
    expect(logo).toHaveAttribute('aria-hidden', 'true')
  })
})
