import { describe, expect, it } from 'vitest'
import { parseHash, projectHref, stepForStage } from './router'

describe('parseHash', () => {
  it('maps top-level pages', () => {
    expect(parseHash('')).toEqual({ name: 'overview' })
    expect(parseHash('#/')).toEqual({ name: 'overview' })
    expect(parseHash('#/projects')).toEqual({ name: 'projects' })
    expect(parseHash('#/settings')).toEqual({ name: 'settings' })
    expect(parseHash('#/new')).toEqual({ name: 'new' })
  })
  it('parses project routes with a step and query', () => {
    const r = parseHash('#/p/prj_0123456789ab/editor?focus=field:delivery_terms')
    expect(r.name).toBe('project')
    if (r.name === 'project') {
      expect(r.id).toBe('prj_0123456789ab')
      expect(r.step).toBe('editor')
      expect(r.query.get('focus')).toBe('field:delivery_terms')
    }
  })
  it('defaults unknown steps to upload and rejects malformed ids', () => {
    const r = parseHash('#/p/prj_0123456789ab/whatever')
    expect(r.name === 'project' && r.step).toBe('upload')
    expect(parseHash('#/p/../../etc').name).toBe('not_found')
    expect(parseHash('#/nope').name).toBe('not_found')
  })
})

describe('links', () => {
  it('builds project links and maps stages to steps', () => {
    expect(projectHref('prj_0123456789ab', 'export', { focus: 'item:itm_1' })).toBe('#/p/prj_0123456789ab/export?focus=item%3Aitm_1')
    expect(stepForStage('extraction')).toBe('review')
    expect(stepForStage('editor')).toBe('editor')
    expect(stepForStage('upload')).toBe('upload')
  })
})
