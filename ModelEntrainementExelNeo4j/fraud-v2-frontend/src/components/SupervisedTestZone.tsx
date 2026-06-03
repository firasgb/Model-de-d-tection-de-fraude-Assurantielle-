import { useState, useCallback } from 'react'
import { Upload, X, Check, AlertCircle, Brain, FileSpreadsheet } from 'lucide-react'

interface SupervisedTestZoneProps {
  onSuccess?: (result: any) => void
  onError?: (error: string) => void
}

interface TestResult {
  index: number
  NUM_SINISTRE: string
  TOTALREGLEMENT: number
  score_suspicion: number
  statut_fraude: string
  niveau_risque: string
}

const ITEMS_PER_PAGE = 20

const SupervisedTestZone = ({ onSuccess, onError }: SupervisedTestZoneProps) => {
  const [isDragging, setIsDragging] = useState(false)
  const [files, setFiles] = useState<File[]>([])
  const [testError, setTestError] = useState<string | null>(null)
  const [testing, setTesting] = useState(false)
  const [testResults, setTestResults] = useState<TestResult[] | null>(null)
  const [modelInfo, setModelInfo] = useState<any>(null)
  const [distribution, setDistribution] = useState<any>(null)
  const [currentPage, setCurrentPage] = useState(1)

  const API_URL = 'http://localhost:8000'

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)

    const droppedFiles = Array.from(e.dataTransfer.files)
    addFiles(droppedFiles)
  }, [])

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const selectedFiles = Array.from(e.target.files)
      addFiles(selectedFiles)
    }
  }

  const addFiles = (newFiles: File[]) => {
    const excelFiles = newFiles.filter(f =>
      f.name.match(/\.(xlsx|xls)$/i)
    )

    if (excelFiles.length === 0) {
      const msg = "Veuillez sélectionner un fichier Excel (.xlsx ou .xls)"
      setTestError(msg)
      onError?.(msg)
      return
    }

    setFiles(prev => [...prev, ...excelFiles])
  }

  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index))
  }

  const [uploading, setUploading] = useState(false)

  const runTest = async () => {
    if (files.length < 1 || files.length > 3) {
      const msg = "Veuillez sélectionner 1-3 fichiers: sinistres.xlsx (obligatoire), contrats.xlsx, tiers.xlsx (optionnel)"
      setTestError(msg)
      onError?.(msg)
      return
    }

    setTesting(true)
    setTestError(null)

    try {
      const formData = new FormData()
      files.forEach(f => {
        formData.append('files', f)
      })

      const response = await fetch(`${API_URL}/model/test-supervised`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(`Erreur ${response.status}: ${errorData.detail || response.statusText}`)
      }

      const result = await response.json()

      if (result.success) {
        setTestResults(result.results)
        setModelInfo(result.model_info)
        setDistribution(result.distribution)
        onSuccess?.(result)
      } else {
        throw new Error(result.error || "Échec du test")
      }

    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Erreur lors du test'
      setTestError(msg)
      onError?.(msg)
    } finally {
      setTesting(false)
    }
  }

  const uploadFiles = async () => {
    if (files.length < 2 || files.length > 3) {
      const msg = "Veuillez sélectionner 2-3 fichiers: sinistres.xlsx, contrats.xlsx, tiers.xlsx (optionnel)"
      setTestError(msg)
      onError?.(msg)
      return
    }

    setUploading(true)
    setTestError(null)

    try {
      const formData = new FormData()
      files.forEach(f => {
        formData.append('files', f)
      })

      const response = await fetch(`${API_URL}/model/upload-data`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(`Erreur ${response.status}: ${errorData.detail || response.statusText}`)
      }

      const result = await response.json()
      console.log('Upload terminé:', result)

    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Erreur lors de l\'upload'
      setTestError(msg)
      onError?.(msg)
    } finally {
      setUploading(false)
    }
  }

  const clearAll = () => {
    setFiles([])
    setTestResults(null)
    setModelInfo(null)
    setDistribution(null)
    setCurrentPage(1)
  }

  const getStatusIcon = (statut: string) => {
    if (statut === 'frauduleux') {
      return <span style={{ color: '#DC2626' }}>🚨</span>
    }
    if (statut === 'suspect') {
      return <span style={{ color: '#D97706' }}>⚠️</span>
    }
    return <span style={{ color: '#059669' }}>✅</span>
  }

  const scoreColor = (score: number) => {
    if (score >= 70) return '#DC2626'
    if (score >= 50) return '#D97706'
    return '#059669'
  }

return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Zone d'upload */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => document.getElementById('supervised-file-input')?.click()}
        style={{
          border: `2px dashed ${isDragging ? '#3B82F6' : '#9CA3AF'}`,
          borderRadius: 12,
          padding: 24,
          textAlign: 'center',
          cursor: 'pointer',
          background: isDragging ? '#EFF6FF' : '#FAFBFC',
          transition: 'all 0.2s'
        }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
          <Brain className="w-10 h-10 text-blue-500" />
          <div>
            <p style={{ margin: 0, fontWeight: 600, color: '#1F2937', marginBottom: 4 }}>
              Zone Test Mode Supervisé
            </p>
            <p style={{ margin: 0, fontSize: 13, color: '#6B7280' }}>
              Déposez sinistres.xlsx (obligatoire), contrats.xlsx, tiers.xlsx (optionnel)
            </p>
            <p style={{ margin: 0, fontSize: 11, color: '#9CA3AF', marginTop: 8 }}>
              Le modèle XGBoost entraîné appliquera ses prédictions (aucun upload en base)
            </p>
          </div>
          <input
            id="supervised-file-input"
            type="file"
            accept=".xlsx,.xls"
            onChange={handleFileSelect}
            className="hidden"
            multiple
          />
        </div>
      </div>

      {/* Liste des fichiers */}
      {files.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h4 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: '#374151' }}>
              Fichiers à tester ({files.length})
            </h4>
            <button
              onClick={clearAll}
              style={{ fontSize: 12, color: '#DC2626', background: 'none', border: 'none', cursor: 'pointer' }}
            >
              Tout supprimer
            </button>
          </div>

          {files.map((file, index) => (
            <div
              key={index}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                padding: 12,
                background: '#F9FAFB',
                borderRadius: 8,
                border: '1px solid #E5E7EB'
              }}
            >
              <FileSpreadsheet className="w-5 h-5 text-blue-500" />
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{ margin: 0, fontSize: 13, fontWeight: 500, color: '#1F2937', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {file.name}
                </p>
                <p style={{ margin: 0, fontSize: 11, color: '#6B7280' }}>
                  {(file.size / 1024).toFixed(1)} KB
                </p>
              </div>
              <button
                onClick={() => removeFile(index)}
                style={{ padding: 4, background: 'none', border: 'none', cursor: 'pointer', color: '#9CA3AF' }}
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Bouton Tester */}
      {files.length > 0 && (
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
          <button
            onClick={clearAll}
            disabled={testing}
            style={{
              padding: '8px 16px',
              background: 'white',
              border: '1px solid #D1D5DB',
              borderRadius: 8,
              color: '#374151',
              cursor: testing ? 'not-allowed' : 'pointer',
              fontSize: 14
            }}
          >
            Annuler
          </button>
          <button
            onClick={runTest}
            disabled={testing}
            style={{
              padding: '8px 16px',
              background: testing ? '#93C5FD' : '#3B82F6',
              color: 'white',
              border: 'none',
              borderRadius: 8,
              cursor: testing ? 'not-allowed' : 'pointer',
              fontSize: 14,
              fontWeight: 500,
              display: 'flex',
              alignItems: 'center',
              gap: 6
            }}
          >
            <Brain className="w-4 h-4" />
            {testing ? 'Test en cours...' : 'Tester le modèle supervisé'}
          </button>
        </div>
      )}

      {/* Résultats du test */}
      {testResults && distribution && (
        <div style={{ background: 'white', borderRadius: 12, padding: 20, border: '1px solid #E5E7EB' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
            <Brain className="w-5 h-5 text-blue-600" />
            <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: '#1F2937' }}>
              Résultats du test supervisé
            </h3>
          </div>

          {/* Infos modèle */}
          {modelInfo && (
            <div style={{ display: 'flex', gap: 12, marginBottom: 16, fontSize: 12, color: '#6B7280' }}>
              <span>Version: v{modelInfo.active_version}</span>
              <span>·</span>
              <span>Source: {modelInfo.label_source}</span>
            </div>
          )}

          {/* Distribution */}
          <div style={{ display: 'flex', gap: 16, marginBottom: 20 }}>
            <div style={{ flex: 1, background: '#FEF2F2', borderRadius: 8, padding: 12, textAlign: 'center' }}>
              <div style={{ fontSize: 24, fontWeight: 800, color: '#DC2626' }}>{distribution.frauduleux?.count || 0}</div>
              <div style={{ fontSize: 11, color: '#9CA3AF' }}>Frauduleux ({distribution.frauduleux?.pct || 0}%)</div>
            </div>
            <div style={{ flex: 1, background: '#FFFBEB', borderRadius: 8, padding: 12, textAlign: 'center' }}>
              <div style={{ fontSize: 24, fontWeight: 800, color: '#D97706' }}>{distribution.suspect?.count || 0}</div>
              <div style={{ fontSize: 11, color: '#9CA3AF' }}>Suspects ({distribution.suspect?.pct || 0}%)</div>
            </div>
            <div style={{ flex: 1, background: '#ECFDF5', borderRadius: 8, padding: 12, textAlign: 'center' }}>
              <div style={{ fontSize: 24, fontWeight: 800, color: '#059669' }}>{distribution.normal?.count || 0}</div>
              <div style={{ fontSize: 11, color: '#9CA3AF' }}>Normaux ({distribution.normal?.pct || 0}%)</div>
            </div>
          </div>

{/* Top résultats */}
          <div style={{ marginBottom: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <h4 style={{ margin: 0, fontSize: 13, fontWeight: 600, color: '#374151' }}>
                Résultats ({(testResults || []).length} sinistres)
              </h4>
              {(testResults && testResults.length > ITEMS_PER_PAGE) && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <button
                    onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                    disabled={currentPage === 1}
                    style={{ padding: '4px 8px', fontSize: 12, border: '1px solid #E5E7EB', borderRadius: 4, background: 'white', cursor: currentPage === 1 ? 'not-allowed' : 'pointer', opacity: currentPage === 1 ? 0.5 : 1 }}
                  >
                    ‹ Précédent
                  </button>
                  <span style={{ fontSize: 12, color: '#6B7280' }}>
                    Page {currentPage} / {Math.ceil(testResults.length / ITEMS_PER_PAGE)}
                  </span>
                  <button
                    onClick={() => setCurrentPage(p => Math.min(Math.ceil(testResults.length / ITEMS_PER_PAGE), p + 1))}
                    disabled={currentPage >= Math.ceil(testResults.length / ITEMS_PER_PAGE)}
                    style={{ padding: '4px 8px', fontSize: 12, border: '1px solid #E5E7EB', borderRadius: 4, background: 'white', cursor: currentPage >= Math.ceil(testResults.length / ITEMS_PER_PAGE) ? 'not-allowed' : 'pointer', opacity: currentPage >= Math.ceil(testResults.length / ITEMS_PER_PAGE) ? 0.5 : 1 }}
                  >
                    Suivant ›
                  </button>
                </div>
              )}
            </div>
            <div style={{ maxHeight: 400, overflowY: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead style={{ position: 'sticky', top: 0, background: '#F9FAFB', zIndex: 1 }}>
                  <tr style={{ background: '#F9FAFB' }}>
                    <th style={{ padding: 8, textAlign: 'left', fontWeight: 600, color: '#374151' }}>#</th>
                    <th style={{ padding: 8, textAlign: 'left', fontWeight: 600, color: '#374151' }}>N° Sinistre</th>
                    <th style={{ padding: 8, textAlign: 'right', fontWeight: 600, color: '#374151' }}>Montant</th>
                    <th style={{ padding: 8, textAlign: 'center', fontWeight: 600, color: '#374151' }}>Score</th>
                    <th style={{ padding: 8, textAlign: 'center', fontWeight: 600, color: '#374151' }}>Statut</th>
                  </tr>
                </thead>
                <tbody>
                  {testResults && testResults.slice((currentPage - 1) * ITEMS_PER_PAGE, currentPage * ITEMS_PER_PAGE).map((r, i) => (
                    <tr key={i} style={{ borderTop: '1px solid #F3F4F6' }}>
                      <td style={{ padding: 8, color: '#9CA3AF' }}>{(currentPage - 1) * ITEMS_PER_PAGE + i + 1}</td>
                      <td style={{ padding: 8, fontFamily: "'DM Mono', monospace", color: '#1F2937' }}>
                        {r.NUM_SINISTRE || '-'}
                      </td>
                      <td style={{ padding: 8, textAlign: 'right', color: '#374151' }}>
                        {r.TOTALREGLEMENT?.toLocaleString() || 0} TND
                      </td>
                      <td style={{ padding: 8, textAlign: 'center' }}>
                        <span style={{
                          fontFamily: "'DM Mono', monospace",
                          fontWeight: 700,
                          color: scoreColor(r.score_suspicion)
                        }}>
                          {r.score_suspicion.toFixed(1)}
                        </span>
                      </td>
                      <td style={{ padding: 8, textAlign: 'center' }}>
                        <span style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 4,
                          padding: '2px 8px',
                          borderRadius: 20,
                          fontSize: 11,
                          fontWeight: 600,
                          background: r.statut_fraude === 'frauduleux' ? '#FEF2F2' : r.statut_fraude === 'suspect' ? '#FFFBEB' : '#ECFDF5',
                          color: r.statut_fraude === 'frauduleux' ? '#DC2626' : r.statut_fraude === 'suspect' ? '#D97706' : '#059669'
                        }}>
                          {getStatusIcon(r.statut_fraude)}
                          {r.statut_fraude}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Erreur */}
      {testError && (
        <div style={{
          background: '#FEF2F2',
          border: '1px solid #FECACA',
          borderRadius: 8,
          padding: 12,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          color: '#DC2626',
          fontSize: 13
        }}>
          <AlertCircle className="w-4 h-4" />
          {testError}
        </div>
      )}

      {/* Note explicative */}
      <div style={{
        background: '#FEF3C7',
        border: '1px solid #FBBF24',
        borderRadius: 8,
        padding: 12,
        fontSize: 12,
        color: '#92400E'
      }}>
        <strong>ℹ️ Note:</strong> Cette zone teste uniquement le modèle XGBoost déjà entraîné.
        Aucune colonne is_fraud n'est générée. Le modèle doit être en mode supervisé (avec labels)
        pour pouvoir utiliser cette fonctionnalité. Uploadez sinistres.xlsx (obligatoire), 
        contrats.xlsx et tiers.xlsx (optionnel) pour les jointures.
      </div>
    </div>
  )
}

export default SupervisedTestZone