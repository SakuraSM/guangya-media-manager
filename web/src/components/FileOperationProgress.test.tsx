import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { Job } from '@/types'
import { FileOperationProgress } from './FileOperationProgress'

const JOB_WITH_FILE_PROGRESS: Job = {
  id: 'job-1',
  name: '实时整理',
  source_directory_path: '/source',
  target_directory_path: '/target',
  status: 'FINALIZING',
  progress: 0.96,
  revision: 4,
  progress_detail: {
    stage: 'CLEANUP',
    state: 'RUNNING',
    completed: 2,
    total: 6,
    current_operation_type: 'TRASH',
    current_filename: 'S01E02.mkv',
    operations: {
      COPY: {
        state: 'COMPLETED',
        completed: 8,
        total: 8,
        succeeded: 7,
        failed: 0,
        skipped: 1,
        current_filename: 'S01E08.mkv',
      },
      TRASH: {
        state: 'RUNNING',
        completed: 2,
        total: 6,
        succeeded: 2,
        failed: 0,
        skipped: 0,
        current_filename: 'S01E02.mkv',
      },
    },
  },
  current_stage: '源文件清理 2/6',
  total_items: 8,
  approved_items: 8,
  executed_items: 8,
  review_items: 0,
  failed_items: 0,
  copied_bytes: 1024,
  error_message: null,
  is_cancel_requested: false,
  auto_approve_enabled: true,
  auto_execute_after_approval: true,
  ai_review_running: false,
  rule_id: null,
  trigger_type: 'MANUAL',
  scanned_directories: 1,
  skipped_directories: 0,
  changed_items: 8,
  created_at: '2026-08-16T00:00:00Z',
  updated_at: '2026-08-16T00:00:01Z',
}

describe('FileOperationProgress', () => {
  it('renders persisted copy and cleanup counters together', () => {
    render(<FileOperationProgress job={JOB_WITH_FILE_PROGRESS} />)

    expect(screen.getByText('文件转移')).toBeVisible()
    expect(screen.getByText('正在清理')).toBeVisible()
    expect(screen.getByText('8/8')).toBeVisible()
    expect(screen.getByText('2/6')).toBeVisible()
    expect(screen.getByText('S01E02.mkv')).toBeVisible()
  })
})
