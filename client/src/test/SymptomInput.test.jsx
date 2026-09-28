import { useState } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { SymptomInput } from '../components/SymptomInput'

function Harness({ initial = [] }) {
  const [value, setValue] = useState(initial)
  return (
    <>
      <SymptomInput value={value} onChange={setValue} vocabulary={['cough', 'fever', 'fatigue']} aliases={{ tired: 'fatigue' }} />
      <output data-testid="value">{value.join('|')}</output>
    </>
  )
}

describe('SymptomInput', () => {
  it('adds typed symptoms on Enter and comma, normalised and de-duplicated', async () => {
    render(<Harness />)
    const user = userEvent.setup()
    const input = screen.getByRole('combobox', { name: 'Symptoms' })
    await user.type(input, '  COUGH {Enter}')
    await user.type(input, 'tired,')
    await user.type(input, 'cough{Enter}')
    expect(screen.getByTestId('value')).toHaveTextContent('cough|fatigue')
  })

  it('offers vocabulary suggestions and picks one with the keyboard', async () => {
    render(<Harness />)
    const user = userEvent.setup()
    const input = screen.getByRole('combobox', { name: 'Symptoms' })
    await user.type(input, 'f')
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual(['fever', 'fatigue'])
    await user.keyboard('{ArrowDown}{Enter}')
    expect(screen.getByTestId('value')).toHaveTextContent('fatigue')
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })

  it('flags symptoms the model does not know', async () => {
    render(<Harness />)
    const user = userEvent.setup()
    await user.type(screen.getByRole('combobox', { name: 'Symptoms' }), 'telepathy{Enter}')
    expect(screen.getByLabelText('Not recognised by the model')).toBeInTheDocument()
    expect(screen.getByText(/outside the model's vocabulary/)).toBeInTheDocument()
  })

  it('removes chips with the remove button and Backspace', async () => {
    render(<Harness initial={['cough', 'fever', 'fatigue']} />)
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Remove fever' }))
    await user.click(screen.getByRole('combobox', { name: 'Symptoms' }))
    await user.keyboard('{Backspace}')
    expect(screen.getByTestId('value')).toHaveTextContent(/^cough$/)
  })
})
