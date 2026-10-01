'use client'

import { useEffect, useState } from 'react'

/**
 * A person's picture, or their initial when they have none.
 *
 * Falls back to the initial when the picture no longer resolves, rather than
 * leaving a broken-image glyph in the header of every page, and gives a newly
 * uploaded picture a fresh chance to load.
 */
export function UserAvatar({
  src,
  name,
  className,
  style,
}: {
  src?: string | null
  name?: string | null
  className?: string
  style?: React.CSSProperties
}) {
  const [broken, setBroken] = useState(false)

  useEffect(() => {
    setBroken(false)
  }, [src])

  return (
    <div className={`overflow-hidden ${className ?? ''}`} style={style}>
      {src && !broken ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src}
          alt=""
          className="h-full w-full object-cover"
          onError={() => setBroken(true)}
        />
      ) : (
        <span aria-hidden="true">{name ? name[0].toUpperCase() : 'U'}</span>
      )}
    </div>
  )
}
