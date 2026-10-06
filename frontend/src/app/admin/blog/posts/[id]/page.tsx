'use client'

import { PostEditor } from '@/components/admin/blog/PostEditor'

export default function EditBlogPostPage({ params }: { params: { id: string } }) {
  // keyed so moving from one post to another starts a fresh form
  return <PostEditor key={params.id} postId={params.id} />
}
