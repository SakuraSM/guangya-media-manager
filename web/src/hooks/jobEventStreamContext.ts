import { createContext } from 'react'
import type { JobProgressEvent } from '@/types'

export type EventStreamState = 'CONNECTING' | 'CONNECTED' | 'DISCONNECTED'

export interface JobEventStreamValue {
  connectionState: EventStreamState
  latestEvent: JobProgressEvent | null
}

export const JobEventStreamContext = createContext<JobEventStreamValue | null>(null)
