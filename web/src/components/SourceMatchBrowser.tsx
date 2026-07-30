import type { MediaMatch } from '../types'
import { formatBytes } from '../utils/format'
import { episodeLabel, type MediaMatchGroup } from '../utils/reviewGrouping'

interface SourceMatchBrowserProps {
  groups: MediaMatchGroup[]
  selectedMatchId: string | null
  pageItemCount: number
  total: number
  onSelectMatch: (mediaMatch: MediaMatch) => void
}

export function SourceMatchBrowser({
  groups,
  selectedMatchId,
  pageItemCount,
  total,
  onSelectMatch,
}: SourceMatchBrowserProps) {
  return (
    <aside className="source-browser">
      <div className="panel-title">
        <h2>源文件</h2>
        <span>
          本页 {pageItemCount} / 共 {total}
        </span>
      </div>
      <ul className="source-list">
        {groups.map((group) => (
          <li className="source-group" key={group.key}>
            <h3>{group.label}</h3>
            <ul>
              {group.items.map((mediaMatch) => (
                <SourceMatchItem
                  key={mediaMatch.id}
                  mediaMatch={mediaMatch}
                  isSelected={mediaMatch.id === selectedMatchId}
                  onSelectMatch={onSelectMatch}
                />
              ))}
            </ul>
          </li>
        ))}
      </ul>
    </aside>
  )
}

interface SourceMatchItemProps {
  mediaMatch: MediaMatch
  isSelected: boolean
  onSelectMatch: (mediaMatch: MediaMatch) => void
}

function SourceMatchItem({
  mediaMatch,
  isSelected,
  onSelectMatch,
}: SourceMatchItemProps) {
  const handleSelect = () => {
    onSelectMatch(mediaMatch)
  }

  return (
    <li>
      <button
        type="button"
        className={isSelected ? 'source-selected' : ''}
        onClick={handleSelect}
      >
        <span className="file-icon" aria-hidden="true">
          ▷
        </span>
        <span>
          <strong>{episodeLabel(mediaMatch)}</strong>
          <small>
            {mediaMatch.filename} · {formatBytes(mediaMatch.size_bytes)}
          </small>
        </span>
      </button>
    </li>
  )
}
