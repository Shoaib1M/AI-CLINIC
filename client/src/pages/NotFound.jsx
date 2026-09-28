import { Link } from 'react-router'

export default function NotFound() {
  return (
    <div className="mx-auto flex min-h-[60vh] max-w-md flex-col items-center justify-center px-4 text-center">
      <p className="text-sm font-semibold text-brand-700">404</p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight">Page not found</h1>
      <p className="mt-2 text-slate-500">The page you are looking for does not exist or has moved.</p>
      <Link to="/" className="btn btn-primary mt-6">Go to the home page</Link>
    </div>
  )
}
