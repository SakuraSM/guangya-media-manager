import { useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Folder, X } from 'lucide-react'
import { api } from '../api/client'
import type { CloudDirectory } from '../types'
import { ErrorNotice } from './ErrorNotice'

interface DirectoryPickerProps {
  id: string
  label: string
  value: CloudDirectory | null
  onSelect: (directory: CloudDirectory) => void
}

const CLOUD_ROOT = {
  id: '',
  path: '/光鸭云盘',
  name: '光鸭云盘',
}

export function DirectoryPicker({
  id,
  label,
  value,
  onSelect,
}: DirectoryPickerProps) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const [isOpen, setIsOpen] = useState(false)
  const [pathStack, setPathStack] = useState([CLOUD_ROOT])
  const current = pathStack[pathStack.length - 1] ?? CLOUD_ROOT
  const directoriesQuery = useQuery({
    queryKey: ['directories', current.id, current.path],
    queryFn: () => api.getDirectories(current.id, current.path),
    enabled: isOpen,
  })

  const openDialog = () => {
    setPathStack([CLOUD_ROOT])
    setIsOpen(true)
    dialogRef.current?.showModal()
  }
  const closeDialog = () => {
    setIsOpen(false)
    dialogRef.current?.close()
  }
  const enterDirectory = (directory: CloudDirectory) => {
    setPathStack((stack) => [
      ...stack,
      { id: directory.id, path: directory.path, name: directory.name },
    ])
  }
  const chooseDirectory = (directory: CloudDirectory) => {
    onSelect(directory)
    closeDialog()
  }

  return (
    <div className="field directory-picker-field">
      <span id={`${id}-label`}>{label}</span>
      <button
        className="directory-picker-trigger"
        type="button"
        aria-labelledby={`${id}-label`}
        onClick={openDialog}
      >
        <Folder size={17} aria-hidden="true" />
        <span>{value?.path ?? '请选择光鸭目录'}</span>
        <ChevronRight size={16} aria-hidden="true" />
      </button>
      <dialog
        ref={dialogRef}
        className="directory-dialog"
        aria-labelledby={`${id}-dialog-title`}
        onClose={() => setIsOpen(false)}
      >
        <div className="directory-dialog-heading">
          <div>
            <span className="eyebrow">{label}</span>
            <h2 id={`${id}-dialog-title`}>浏览云盘目录</h2>
          </div>
          <button className="dialog-close" type="button" onClick={closeDialog} aria-label="关闭">
            <X size={18} aria-hidden="true" />
          </button>
        </div>
        <div className="directory-breadcrumb">
          <button
            type="button"
            disabled={pathStack.length === 1}
            onClick={() => setPathStack((stack) => stack.slice(0, -1))}
          >
            <ChevronLeft size={16} aria-hidden="true" />
            返回
          </button>
          <code>{current.path}</code>
        </div>
        {directoriesQuery.isError ? (
          <ErrorNotice message={directoriesQuery.error.message} />
        ) : null}
        <div className="directory-list" aria-live="polite">
          {directoriesQuery.isPending ? (
            <span className="directory-empty">正在读取目录…</span>
          ) : null}
          {directoriesQuery.data?.map((directory) => (
            <div className="directory-row" key={directory.id}>
              <button type="button" onClick={() => enterDirectory(directory)}>
                <Folder size={17} aria-hidden="true" />
                <span>
                  <strong>{directory.name}</strong>
                  <small>{directory.item_count} 个项目</small>
                </span>
                <ChevronRight size={16} aria-hidden="true" />
              </button>
              <button
                className="button button-secondary"
                type="button"
                onClick={() => chooseDirectory(directory)}
              >
                选择
              </button>
            </div>
          ))}
          {!directoriesQuery.isPending && !directoriesQuery.data?.length ? (
            <span className="directory-empty">这个目录下没有子目录</span>
          ) : null}
        </div>
        {current.id ? (
          <button
            className="button button-primary button-full"
            type="button"
            onClick={() =>
              chooseDirectory({
                id: current.id,
                parent_id: '',
                name: current.name,
                path: current.path,
                item_count: 0,
              })
            }
          >
            选择当前目录
          </button>
        ) : null}
      </dialog>
    </div>
  )
}
