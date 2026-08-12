import { useContext } from 'react'
import { JobEventStreamContext, type JobEventStreamValue } from './jobEventStreamContext'

export function useJobEventStream(): JobEventStreamValue {
  const eventStream = useContext(JobEventStreamContext)
  if (!eventStream) throw new Error('JobEventStreamProvider is missing')
  return eventStream
}
