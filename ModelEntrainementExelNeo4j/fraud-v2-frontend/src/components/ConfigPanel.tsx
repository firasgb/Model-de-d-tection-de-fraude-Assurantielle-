import { useState, useEffect } from 'react'
import ThresholdEditor from './ThresholdEditor'
import GroupWeightsEditor from './GroupWeightsEditor'
import IndicatorWeightsEditor from './IndicatorWeightsEditor'
import FileUploadZone from './FileUploadZone'

const API_URL = (typeof import.meta !== 'undefined' && import.meta?.env?.VITE_API_URL) || 'http://localhost:8000'

interface ConfigPanelProps {
  onConfigApplied?: () => void
  onDataUploaded?: () => void
  onTrainingStarted?: () => void
  onTrainingEnded?: () => void
  labelColumn?: string
  onLabelColumnChange?: (value: string) => void
  labelColumnOptions?: string[]
}

const ConfigPanel = ({ onConfigApplied, onDataUploaded, onTrainingStarted, onTrainingEnded, labelColumn = '', onLabelColumnChange, labelColumnOptions = [] }: ConfigPanelProps) => {
  const [activeSubTab, setActiveSubTab] = useState('thresholds')
  const [currentConfig, setCurrentConfig] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'success' | 'error'>('idle')
  const [trainingStatus, setTrainingStatus] = useState<any>(null)
  const [trainingJobId, setTrainingJobId] = useState<string | null>(null)
  const [trainingProgress, setTrainingProgress] = useState(0)
  const [labelsPreview, setLabelsPreview] = useState<any>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [reloadLoading, setReloadLoading] = useState(false)
  const [reloadMessage, setReloadMessage] = useState<string | null>(null)

  // Charger la config actuelle au montage
  useEffect(() => {
    fetchCurrentConfig()
  }, [])

  // Polling du statut d'entraînement
  useEffect(() => {
    if (!trainingJobId) return
    
    const pollInterval = setInterval(async () => {
      try {
        const res = await fetch(`${API_URL}/model/train/status`)
        if (res.ok) {
          const data = await res.json()
          setTrainingStatus(data)
          setTrainingProgress(data.progress || 0)
          
          // Si terminé ou en erreur, arrêter le polling
          if (data.status === 'completed' || data.status === 'failed') {
            setTrainingJobId(null)
            onTrainingEnded?.()
            if (data.status === 'completed') {
              onConfigApplied?.()
            }
          }
        }
      } catch (err) {
        console.error('Erreur polling status:', err)
      }
    }, 1000) // Poll every 1 second

    return () => clearInterval(pollInterval)
  }, [trainingJobId, onConfigApplied, onTrainingEnded])

  const fetchCurrentConfig = async () => {
    try {
      setLoading(true)
      const res = await fetch(`${API_URL}/model/current-config`)
      if (!res.ok) throw new Error(`Erreur ${res.status}`)
      const data = await res.json()
      setCurrentConfig(data.config)
      setFetchError(null)
    } catch (err: any) {
      setFetchError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const fetchLabelsPreview = async () => {
    try {
      setPreviewLoading(true)
      const res = await fetch(`${API_URL}/model/labels/preview`)
      if (!res.ok) throw new Error(`Erreur ${res.status}`)
      const data = await res.json()
      setLabelsPreview(data)
    } catch (err: any) {
      setActionError(err?.message || 'Erreur preview labels')
    } finally {
      setPreviewLoading(false)
    }
  }

  const handleConfigUpdate = async (updates: any) => {
    try {
      setSaveStatus('saving')
      const res = await fetch(`${API_URL}/model/reconfigure`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      })
      if (!res.ok) {
        const errBody = await res.json()
        const errorMessage = typeof errBody?.detail === 'string'
          ? errBody.detail
          : errBody?.detail?.error || errBody?.error || undefined
        const detailList = Array.isArray(errBody?.detail?.details)
          ? errBody.detail.details.join('; ')
          : Array.isArray(errBody?.details)
            ? errBody.details.join('; ')
            : ''
        const finalMessage = [errorMessage, detailList].filter(Boolean).join(': ') || 'Erreur reconfigure'
        throw new Error(finalMessage)
      }
      const result = await res.json()
      setSaveStatus('success')
      setCurrentConfig(result.config_snapshot)
      
      // Démarrer le suivi du job d'entraînement
      if (result.job_id) {
        onTrainingStarted?.()
        setTrainingJobId(result.job_id)
        setTrainingProgress(0)
        setTrainingStatus({ status: 'running', message: 'Démarrage du re-scoring et sauvegarde...' })
      }
      
      setTimeout(() => setSaveStatus('idle'), 3000)
    } catch (err: any) {
      const message = err?.message || 'Erreur lors de l\'application de la configuration'
      setActionError(message)
      setSaveStatus('error')
    }
  }

  const handleThresholdsSave = (thresholds: any) => {
    handleConfigUpdate({ thresholds })
  }

  const handleGroupWeightsSave = (groupWeights: any) => {
    handleConfigUpdate({ group_weights: groupWeights })
  }

  const handleIndicatorWeightsSave = (indicatorWeights: any) => {
    handleConfigUpdate({ indicator_weights: indicatorWeights })
  }

  const handleUploadComplete = (result: any) => {
    console.log('Upload terminé:', result)
    if (typeof onDataUploaded === 'function') {
      try { onDataUploaded() } catch (e) { console.warn('onDataUploaded handler error', e) }
    }
    // Après upload, forcer le rechargement des données côté backend
    (async () => {
      try {
        setReloadLoading(true)
        setReloadMessage(null)
        const res = await fetch(`${API_URL}/data/reload`, { method: 'POST' })
        if (!res.ok) throw new Error(`Erreur ${res.status}`)
        const body = await res.json()
        setReloadMessage(body.message || 'Données rechargées')
        // actualiser l'aperçu de labels automatiquement
        try { await fetchLabelsPreview() } catch (e) { /* ignore */ }
      } catch (err: any) {
        setReloadMessage(err?.message || 'Erreur reload')
        setActionError(err?.message || 'Erreur reload')
      } finally {
        setReloadLoading(false)
        setTimeout(() => setReloadMessage(null), 4000)
      }
    })()
  }

  const handleError = (msg: string) => {
    setActionError(msg)
    setSaveStatus('error')
  }

  const trainModel = async () => {
    try {
      const response = await fetch(`${API_URL}/model/train`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      })
      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData?.detail || `Erreur ${response.status}`)
      }
      const data = await response.json()
      onTrainingStarted?.()
      setTrainingJobId(data.job_id || 'training')
      setTrainingProgress(0)
      setTrainingStatus({ status: 'running', message: data.message || 'Réentraînement en cours...' })
    } catch (error: any) {
      const message = error?.message || 'Erreur lors du réentraînement'
      setActionError(message)
    }
  }

  useEffect(() => {
    if (!actionError) return
    const timer = window.setTimeout(() => setActionError(null), 4000)
    return () => window.clearTimeout(timer)
  }, [actionError])

  if (loading) {
    return <div className="p-8 text-center text-gray-500">Chargement de la configuration...</div>
  }

  if (fetchError) {
    return <div className="p-8 text-center text-red-600 bg-red-50 rounded-lg">Erreur: {fetchError}</div>
  }

  return (
    <div className="space-y-6">
      {/* En-tête */}
      <div className="bg-white p-6 rounded-lg border">
        <h2 className="text-xl font-bold text-gray-800 mb-2">Configuration du Scoring</h2>
        <p className="text-sm text-gray-600">
          Ajustez les poids des groupes d'indicateurs, les seuils de classification, et téléversez de nouvelles données.
          Les modifications de seuils sont appliquées immédiatement; les modifications de poids déclenchent un ré-entraînement du modèle.
        </p>
        {currentConfig && (
          <div className="mt-3 text-xs text-gray-500">
            Version config: <span className="font-mono">{currentConfig.version || '1.0'}</span> ·
            Dernière mise à jour: <span className="font-mono">{new Date(currentConfig.created_at).toLocaleString('fr-FR')}</span>
          </div>
        )}
      </div>

      {/* Indicateur de progression d'entraînement */}
      {trainingJobId && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <h3 className="font-semibold text-blue-900">
              {trainingStatus?.status === 'completed' ? '✅ Entraînement terminé' : 
               trainingStatus?.status === 'failed' ? '❌ Entraînement échoué' :
               '⚙️ Entraînement en cours...'}
            </h3>
            <div style={{ textAlign: 'right' }}>
              <div className="text-sm text-blue-700">{trainingProgress}%</div>
              {trainingStatus?.label_source && (
                <div className="text-xs text-slate-600">Labels: {trainingStatus.label_source}</div>
              )}
            </div>
          </div>
          <div className="w-full bg-blue-200 rounded-full h-2 mb-2">
            <div 
              className="bg-blue-600 h-2 rounded-full transition-all duration-300" 
              style={{ width: `${trainingProgress}%` }}
            ></div>
          </div>
          <p className="text-sm text-blue-700">{trainingStatus?.message}</p>
          {trainingStatus?.label_source && (
            <div className="mt-3 flex flex-wrap gap-2 text-xs">
              <span className={`inline-flex items-center rounded-full px-2.5 py-1 font-semibold ${trainingStatus.label_source === 'auto' ? 'bg-orange-100 text-orange-800' : 'bg-emerald-100 text-emerald-800'}`}>
                {trainingStatus.label_source === 'auto' ? 'Pseudo-supervisé' : 'Supervisé'}
              </span>
              <span className="text-slate-600">
                {trainingStatus.label_source === 'auto'
                  ? 'Label auto-généré (`is_fraud`) pour l’entraînement pseudo-supervisé.'
                  : 'Label manuel existant utilisé pour l’entraînement.'}
              </span>
            </div>
          )}
          {trainingStatus?.status === 'completed' && (
            <div className="mt-2 text-sm text-green-700 bg-green-50 p-2 rounded">
              ✓ Nouvelle version du modèle créée et activée. Les statistiques seront mises à jour.
            </div>
          )}
          {trainingStatus?.status === 'failed' && (
            <div className="mt-2 text-sm text-red-700 bg-red-50 p-2 rounded">
              ✗ Erreur: {trainingStatus?.error}
            </div>
          )}
        </div>
      )}

      {/* Sous-onglets */}
      <div className="bg-white rounded-lg border">
        <div className="flex border-b">
          {[
            { id: 'thresholds', label: 'Seuils', icon: '📊' },
            { id: 'groups', label: 'Poids Groupes', icon: '⚖️' },
            { id: 'indicators', label: 'Poids Indicateurs', icon: '🎯' },
            { id: 'upload', label: 'Données Excel', icon: '📤' },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveSubTab(tab.id)}
              className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
                activeSubTab === tab.id
                  ? 'text-blue-600 border-b-2 border-blue-600 bg-blue-50'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              <span className="mr-2">{tab.icon}</span>{tab.label}
            </button>
          ))}
        </div>

        <div className="p-6">
          {activeSubTab === 'thresholds' && currentConfig && (
            <ThresholdEditor
              initialThresholds={currentConfig.thresholds || {}}
              onSave={handleThresholdsSave}
              onError={handleError}
            />
          )}

          {activeSubTab === 'groups' && currentConfig && (
            <GroupWeightsEditor
              initialWeights={currentConfig.group_weights}
              onSave={handleGroupWeightsSave}
              onError={handleError}
            />
          )}

          {activeSubTab === 'indicators' && currentConfig && (
            <IndicatorWeightsEditor
              initialWeights={currentConfig.indicator_weights || {}}
              onSave={handleIndicatorWeightsSave}
              onError={handleError}
            />
          )}

          {activeSubTab === 'upload' && (
            <>
              <div className="mb-6 p-4 rounded-lg border border-dashed border-slate-200 bg-slate-50">
                <label className="flex flex-col gap-2 text-sm text-slate-700">
                  <span className="font-semibold">Colonne de labels (optionnel):</span>
                  <input
                    type="text"
                    list="label-columns-list"
                    placeholder="Ex: is_fraud, fraud_label"
                    value={labelColumn}
                    onChange={(e) => onLabelColumnChange?.(e.target.value)}
                    className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-mono text-slate-900 focus:border-blue-500 focus:outline-none"
                  />
                  <span className="text-xs text-slate-500">✓ Pour un entraînement supervisé</span>
                </label>
                <datalist id="label-columns-list">
                  {labelColumnOptions.map(col => (
                    <option key={col} value={col} />
                  ))}
                </datalist>
                {labelColumnOptions.length > 0 && (
                  <div className="mt-3 text-xs text-slate-600">
                    Colonnes détectées dans <strong>sinistres</strong> : {labelColumnOptions.slice(0, 10).join(', ')}{labelColumnOptions.length > 10 ? ', ...' : ''}
                  </div>
                )}
                  <div className="mt-3 flex items-center gap-2">
                    <button
                      onClick={fetchLabelsPreview}
                      disabled={previewLoading}
                      className="px-3 py-1 text-sm bg-blue-600 text-white rounded"
                    >
                      {previewLoading ? 'Chargement...' : 'Aperçu labels'}
                    </button>
                    <span className="text-xs text-slate-500">Vérifie si un label manuel existe ou sera généré</span>
                  </div>
                  {labelsPreview && (
                    <div className="mt-3 p-3 bg-gray-50 border rounded text-xs">
                      <div><strong>Type de label:</strong> {labelsPreview.label_source === 'auto' ? 'Auto-généré' : 'Manuel'}</div>
                      <div><strong>Source:</strong> {labelsPreview.label_source}</div>
                      <div><strong>Colonne:</strong> {labelsPreview.label_column}</div>
                      <div className="mt-2"><strong>Summary:</strong> {JSON.stringify(labelsPreview.summary)}</div>
                      <div className="mt-2"><strong>Samples:</strong> <pre className="text-[10px]">{JSON.stringify(labelsPreview.samples)}</pre></div>
                      {labelsPreview.label_source === 'auto' ? (
                        <div className="mt-3 rounded-lg border border-orange-200 bg-orange-50 p-2 text-orange-800">
                          ⚠️ Aucun label manuel détecté. Le backend va générer un label `is_fraud` et l’utiliser pour l’entraînement.
                        </div>
                      ) : (
                        <div className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 p-2 text-emerald-800">
                          ✅ Label manuel détecté. Entraînement supervisé avec ce label.
                        </div>
                      )}
                    </div>
                  )}
              </div>
              <FileUploadZone
                onUploadComplete={handleUploadComplete}
                onError={handleError}
              />
              {reloadLoading && (
                <div className="mt-3 text-sm text-slate-600">Rechargement des données en cours...</div>
              )}
              {reloadMessage && (
                <div className="mt-3 text-sm text-green-700 bg-green-50 p-2 rounded">{reloadMessage}</div>
              )}
              <div className="mt-6 pt-6 border-t flex justify-end gap-3">
                <button
                  onClick={trainModel}
                  disabled={trainingJobId !== null}
                  className="px-6 py-2 bg-green-600 text-white rounded-lg font-semibold hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 transition"
                >
                  {trainingJobId ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      Réentraînement...
                    </>
                  ) : (
                    <>
                      🔄 Réentraîner le modèle
                    </>
                  )}
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Feedback */}
      {saveStatus === 'success' && (
        <div className="fixed bottom-6 right-6 bg-green-600 text-white px-6 py-3 rounded-lg shadow-lg flex items-center gap-2">
          <span>✓ Configuration appliquée</span>
        </div>
      )}
      {saveStatus === 'error' && actionError && (
        <div className="fixed bottom-6 right-6 bg-red-600 text-white px-6 py-3 rounded-lg shadow-lg flex items-center gap-3">
          <span>✕ {actionError}</span>
          <button
            onClick={() => setActionError(null)}
            className="text-white opacity-80 hover:opacity-100"
          >
            Fermer
          </button>
        </div>
      )}
    </div>
  )
}

export default ConfigPanel
