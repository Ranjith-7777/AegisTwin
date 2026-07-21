import { SearchX } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '../components/ui/button'

export function NotFoundPage() {
  return (
    <div className="flex min-h-[55vh] flex-col items-center justify-center text-center">
      <SearchX className="size-10 text-slate-500" />
      <p className="eyebrow mt-5">Error 404</p>
      <h1 className="mt-2 text-3xl font-semibold text-white">Route not found</h1>
      <p className="mt-3 max-w-md text-slate-400">
        The requested dashboard route does not exist in this foundation.
      </p>
      <Button asChild className="mt-6">
        <Link to="/">Return to overview</Link>
      </Button>
    </div>
  )
}
