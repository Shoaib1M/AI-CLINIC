import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { PredictionCard } from '../components/PredictionCard'

describe('PredictionCard', () => {
  it('labels output as model confidence, not a diagnosis', () => {
    render(
      <PredictionCard
        showTreatments
        prediction={{
          status: 'ok',
          predicted_disease: 'Migraine',
          confidence: 0.35,
          confidence_level: 'low',
          top_predictions: [{ disease: 'Migraine', probability: 0.35 }, { disease: 'Sinusitis', probability: 0.3 }],
          warnings: ['Only 2 recognised symptom(s).'],
          reference_treatments: [],
          model_version: 'rf-test',
        }}
      />,
    )
    expect(screen.getByText('Not a diagnosis')).toBeInTheDocument()
    expect(screen.getByText(/Weak agreement/)).toBeInTheDocument()
    expect(screen.getByText(/not the probability that the patient has this condition/)).toBeInTheDocument()
    expect(screen.getByText('Only 2 recognised symptom(s).')).toBeInTheDocument()
    expect(screen.getByText('None recorded for this condition in the dataset.')).toBeInTheDocument()
  })

  it('explains when no suggestion could be made', () => {
    render(<PredictionCard prediction={{ status: 'no_known_symptoms', warnings: [] }} />)
    expect(screen.getByText(/no suggestion was made/)).toBeInTheDocument()
    expect(screen.queryByText('Most likely pattern')).not.toBeInTheDocument()
  })
})
