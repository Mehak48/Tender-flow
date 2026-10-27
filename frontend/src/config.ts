import branding from '../../branding.json'

/** Product name and tagline come from ../branding.json — the single place to rename the product. */
export const APP_NAME: string = branding.name
export const TAGLINE: string = branding.tagline
export const SHORT_TAGLINE: string = branding.shortTagline

/** Same-origin by default: Vite proxies /api in development and FastAPI serves the built app. */
export const API_BASE: string = (import.meta.env.VITE_API_BASE as string | undefined) ?? ''

/** Client-side mirror of the backend limits; the backend re-checks everything. */
export const ACCEPT: Record<'tender' | 'template' | 'price_list', string[]> = {
  tender: ['pdf', 'docx'],
  template: ['docx', 'xlsx'],
  price_list: ['xlsx', 'csv'],
}
export const DEFAULT_MAX_UPLOAD_MB = 25
