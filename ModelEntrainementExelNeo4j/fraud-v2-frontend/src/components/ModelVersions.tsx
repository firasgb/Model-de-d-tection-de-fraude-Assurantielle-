import { useState, useEffect } from 'react'

interface Version {
  version: number
  created_at: string
  active: boolean
  f1_score: number | null
  precision: number | null
  recall: number | null
  accuracy: number | null
  auc_roc: number | null
  score_moyen: number
  notes: string
  analyst_comment?: string
  report?: VersionReport
  config_snapshot?: any
  is_supervised?: boolean
  label_source?: string | null
}

interface VersionChange {
  before: any
  after: any
}

interface VersionReport {
  changes?: Record<string, VersionChange>
  [key: string]: any
}

interface VersionData {
  active_version: number | null
  versions: Version[]
  current_stats?: {
    score_moyen: number
    frauduleux_percent: number
    suspects_percent: number
    normaux_percent: number
  }
}

const ModelVersions = ({ onStatsRefresh }: { onStatsRefresh?: () => void }) => {
  const [versions, setVersions] = useState<VersionData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [comparing, setComparing] = useState<{v1: number, v2: number} | null>(null)
  const [comparisonData, setComparisonData] = useState<any | null>(null)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(5)
  const [searchQuery, setSearchQuery] = useState('')
  const [trainingFilter, setTrainingFilter] = useState<'all' | 'supervised' | 'pseudo' | 'unsupervised'>('all')
  const [showBestOnly, setShowBestOnly] = useState(false)
  const [selectedV1, setSelectedV1] = useState<number | null>(null)
  const [selectedV2, setSelectedV2] = useState<number | null>(null)
  const [openReportVersion, setOpenReportVersion] = useState<number | null>(null)

  const API_URL = (typeof import.meta !== 'undefined' && import.meta?.env?.VITE_API_URL) || 'http://localhost:8000'

  const fetchVersions = async () => {
    try {
      setLoading(true)
      const response = await fetch(`${API_URL}/model/versions`)
      if (!response.ok) throw new Error('Erreur lors du chargement des versions')
      const data = await response.json()
      setVersions(data)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur inconnue')
    } finally {
      setLoading(false)
    }
  }

  const activateVersion = async (versionNum: number) => {
    try {
      const response = await fetch(`${API_URL}/model/versions/${versionNum}/activate`, {
        method: 'POST'
      })
      if (!response.ok) throw new Error('Erreur lors de l\'activation')
      await fetchVersions() // Recharger les données des versions
      if (onStatsRefresh) {
        onStatsRefresh() // Rafraîchir les statistiques du dashboard
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur d\'activation')
    }
  }

  const deleteVersion = async (versionNum: number) => {
    if (!window.confirm(`Êtes-vous sûr de vouloir supprimer la version ${versionNum}? Cette action est irréversible.`)) {
      return
    }
    
    try {
      const response = await fetch(`${API_URL}/model/versions/${versionNum}`, {
        method: 'DELETE'
      })
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Erreur lors de la suppression')
      }
      await fetchVersions() // Recharger les données des versions
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur de suppression')
    }
  }

  const compareVersions = async (v1: number, v2: number) => {
    try {
      const response = await fetch(`${API_URL}/model/versions/compare?v1=${v1}&v2=${v2}`)
      if (!response.ok) throw new Error(`Erreur lors de la comparaison: ${response.status}`)
      const data = await response.json()
      setComparing({v1, v2})
      setComparisonData(data)
      console.log('Comparaison réussie:', data)
      return data
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : 'Erreur de comparaison'
      console.error('Erreur de comparaison:', errMsg)
      setError(errMsg)
      return null
    }
  }

  useEffect(() => {
    fetchVersions()
  }, [])

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('fr-FR', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const formatMetric = (value: number | null | string) => {
    if (value === null || value === 'N/A' || value === undefined) {
      return 'N/A'
    }
    if (typeof value === 'string') {
      return value
    }
    return typeof value === 'number' ? value.toFixed(4) : 'N/A'
  }

  const hasSupervisedMetrics = (version: Version) => {
    return [version.f1_score, version.precision, version.recall, version.accuracy, version.auc_roc]
      .some((value) => typeof value === 'number')
  }

  const getSupervisionMode = (version: Version) => {
    if (version.is_supervised) {
      if (version.label_source === 'auto') {
        return 'Pseudo-supervisé'
      }
      if (version.label_source === 'manual') {
        return 'Supervisé'
      }
      return 'Supervisé'
    }

    if (hasSupervisedMetrics(version)) {
      return 'Supervisé (incohérence détectée)'
    }
    return 'Non supervisé'
  }

  const getSupervisionDescription = (version: Version) => {
    if (version.is_supervised) {
      if (version.label_source === 'auto') {
        return 'Entraînement pseudo-supervisé : des labels de fraude sont générés automatiquement puis utilisés pour entraîner le modèle.'
      }
      if (version.label_source === 'manual') {
        return 'Entraînement supervisé : le modèle apprend à partir de labels de fraude manuels existants dans les données.'
      }
      return 'Entraînement supervisé : le modèle est entraîné avec des labels de fraude disponibles.'
    }

    if (hasSupervisedMetrics(version)) {
      return 'Données de supervision présentes dans les métriques, mais le mode explicite n’est pas défini. Le modèle semble avoir été entraîné avec des labels.'
    }

    return 'Entraînement non supervisé : le modèle utilise des scores heuristiques et des règles sans labels de fraude explicites.'
  }

  const bestVersion = versions?.versions.reduce<Version | null>((best, current) => {
    if (!best) return current
    if (current.score_moyen > best.score_moyen) return current
    return best
  }, null)

  const filteredVersions = versions?.versions.filter((version) => {
    const searchText = `${version.version} ${version.notes}`.toLowerCase()
    if (searchQuery && !searchText.includes(searchQuery.toLowerCase())) {
      return false
    }

    const mode = getSupervisionMode(version)
    if (trainingFilter === 'supervised' && !version.is_supervised) {
      return false
    }
    if (trainingFilter === 'pseudo' && version.label_source !== 'auto') {
      return false
    }
    if (trainingFilter === 'unsupervised' && version.is_supervised) {
      return false
    }

    return true
  }) || []

  const displayedVersions = showBestOnly
    ? filteredVersions.filter((version) => bestVersion ? version.version === bestVersion.version : true)
    : filteredVersions

  // Helper functions for formatting report data
  const formatReportKey = (key: string): string => {
    return key
      .replace(/_/g, ' ')
      .replace(/\b\w/g, c => c.toUpperCase())
  }

  const formatReportValue = (value: any): string => {
    if (value === null) return 'Null'
    if (value === undefined) return 'Indéfini'
    if (typeof value === 'boolean') return value ? 'Oui' : 'Non'
    if (typeof value === 'number') return value.toString()
    if (typeof value === 'string') return value
    if (Array.isArray(value)) return `${value.length} élément${value.length !== 1 ? 's' : ''}`
    if (typeof value === 'object') {
      try {
        return JSON.stringify(value)
      } catch {
        return '[Objet complexe]'
      }
    }
    return String(value)
  }

  const totalPages = Math.max(1, Math.ceil(displayedVersions.length / pageSize))
  const pageVersions = displayedVersions.slice((page - 1) * pageSize, page * pageSize)

  const handlePageChange = (newPage: number) => {
    setPage(Math.max(1, Math.min(newPage, totalPages)))
  }

  useEffect(() => {
    setPage(1)
  }, [searchQuery, trainingFilter, showBestOnly])

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        <span className="ml-2">Chargement des versions...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 m-4">
        <div className="flex items-center">
          <svg className="w-5 h-5 text-red-400 mr-2" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
          </svg>
          <span className="text-red-800">{error}</span>
        </div>
        <button
          onClick={fetchVersions}
          className="mt-2 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
        >
          Réessayer
        </button>
      </div>
    )
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          Gestion des Versions du Modèle
        </h1>
        <p className="text-gray-600">
          Comparez et activez différentes versions du modèle de détection de fraude
        </p>
      </div>

      {versions && (
        <>
          {/* Statistiques actuelles du modèle */}
          {versions.current_stats && (
            <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg p-6 mb-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center">
                <svg className="w-5 h-5 text-blue-600 mr-2" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M3 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" clipRule="evenodd" />
                </svg>
                Statistiques du Modèle Actuel
              </h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center">
                  <div className={`text-3xl font-bold ${versions.current_stats.score_moyen >= 35 && versions.current_stats.score_moyen <= 45 ? 'text-green-600' : versions.current_stats.score_moyen < 35 ? 'text-orange-600' : 'text-red-600'}`}>
                    {versions.current_stats.score_moyen.toFixed(1)}
                  </div>
                  <div className="text-sm text-gray-600">Score Moyen /100</div>
                  <div className="text-xs text-gray-500 mt-1">Cible: 35-45</div>
                  {versions.current_stats.score_moyen < 35 && (
                    <div className="text-xs text-orange-600 mt-1">⚠️ Trop bas</div>
                  )}
                  {versions.current_stats.score_moyen > 45 && (
                    <div className="text-xs text-red-600 mt-1">⚠️ Trop élevé</div>
                  )}
                </div>
                <div className="text-center">
                  <div className={`text-3xl font-bold ${versions.current_stats.frauduleux_percent >= 5 && versions.current_stats.frauduleux_percent <= 15 ? 'text-green-600' : versions.current_stats.frauduleux_percent < 5 ? 'text-orange-600' : 'text-red-600'}`}>
                    {versions.current_stats.frauduleux_percent.toFixed(1)}%
                  </div>
                  <div className="text-sm text-gray-600">Frauduleux</div>
                  <div className="text-xs text-gray-500 mt-1">Cible: 5-15%</div>
                  {versions.current_stats.frauduleux_percent < 5 && (
                    <div className="text-xs text-orange-600 mt-1">⚠️ Trop peu</div>
                  )}
                  {versions.current_stats.frauduleux_percent > 15 && (
                    <div className="text-xs text-red-600 mt-1">⚠️ Trop</div>
                  )}
                </div>
                <div className="text-center">
                  <div className={`text-3xl font-bold ${versions.current_stats.suspects_percent >= 15 && versions.current_stats.suspects_percent <= 25 ? 'text-green-600' : 'text-orange-600'}`}>
                    {versions.current_stats.suspects_percent.toFixed(1)}%
                  </div>
                  <div className="text-sm text-gray-600">Suspects</div>
                  <div className="text-xs text-gray-500 mt-1">Cible: 15-25%</div>
                  {(versions.current_stats.suspects_percent < 15 || versions.current_stats.suspects_percent > 25) && (
                    <div className="text-xs text-orange-600 mt-1">⚠️ Ajuster</div>
                  )}
                </div>
                <div className="text-center">
                  <div className={`text-3xl font-bold ${versions.current_stats.normaux_percent >= 60 && versions.current_stats.normaux_percent <= 80 ? 'text-green-600' : 'text-orange-600'}`}>
                    {versions.current_stats.normaux_percent.toFixed(1)}%
                  </div>
                  <div className="text-sm text-gray-600">Normaux</div>
                  <div className="text-xs text-gray-500 mt-1">Cible: 60-80%</div>
                  {(versions.current_stats.normaux_percent < 60 || versions.current_stats.normaux_percent > 80) && (
                    <div className="text-xs text-orange-600 mt-1">⚠️ Ajuster</div>
                  )}
                </div>
              </div>

              {/* Recommandations */}
              <div className="mt-6 p-4 bg-white border border-gray-200 rounded-lg">
                <h3 className="text-lg font-semibold text-gray-900 mb-3 flex items-center">
                  <svg className="w-5 h-5 text-blue-600 mr-2" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                  </svg>
                  Recommandations
                </h3>
                <div className="space-y-2 text-sm">
                  {versions.current_stats.score_moyen < 35 && (
                    <div className="flex items-center text-orange-700">
                      <span className="mr-2">⚠️</span>
                      Score moyen trop bas - Considérer un réentraînement avec des seuils ajustés
                    </div>
                  )}
                  {versions.current_stats.score_moyen > 45 && (
                    <div className="flex items-center text-red-700">
                      <span className="mr-2">🚨</span>
                      Score moyen trop élevé - Risque de sur-détection, ajuster les seuils
                    </div>
                  )}
                  {versions.current_stats.frauduleux_percent < 5 && (
                    <div className="flex items-center text-orange-700">
                      <span className="mr-2">⚠️</span>
                      Taux de détection frauduleux faible - Vérifier la qualité des données d'entraînement
                    </div>
                  )}
                  {versions.current_stats.frauduleux_percent > 15 && (
                    <div className="flex items-center text-red-700">
                      <span className="mr-2">🚨</span>
                      Taux de détection frauduleux élevé - Risque de faux positifs, recalibrer le modèle
                    </div>
                  )}
                  {versions.current_stats.suspects_percent < 15 || versions.current_stats.suspects_percent > 25 ? (
                    <div className="flex items-center text-orange-700">
                      <span className="mr-2">⚠️</span>
                      Taux de suspects hors cible - Ajustement des seuils recommandé
                    </div>
                  ) : (
                    <div className="flex items-center text-green-700">
                      <span className="mr-2">✅</span>
                      Distribution équilibrée - Modèle bien calibré
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div className="flex items-center gap-2">
                <svg className="w-5 h-5 text-blue-600" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                </svg>
                <span className="text-blue-800 font-medium">
                  Version active : {versions.active_version || 'Aucune'}
                </span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 w-full md:w-auto">
                <input
                  type="search"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Rechercher une version ou une note"
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 focus:border-blue-500 focus:ring-blue-200 focus:outline-none"
                />
                <select
                  value={trainingFilter}
                  onChange={(e) => setTrainingFilter(e.target.value as any)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 focus:border-blue-500 focus:ring-blue-200 focus:outline-none"
                >
                  <option value="all">Toutes les versions</option>
                  <option value="supervised">Supervisé</option>
                  <option value="pseudo">Pseudo-supervisé</option>
                  <option value="unsupervised">Non supervisé</option>
                </select>
                <button
                  onClick={() => setShowBestOnly(!showBestOnly)}
                  className={`w-full rounded-lg px-3 py-2 font-semibold transition ${showBestOnly ? 'bg-indigo-600 text-white hover:bg-indigo-700' : 'bg-white border border-slate-300 text-slate-700 hover:bg-slate-50'}`}
                >
                  {showBestOnly ? 'Afficher toutes' : 'Afficher meilleure version'}
                </button>
              </div>
            </div>
          </div>

          {/* Sélection libre de deux versions pour comparaison */}
          <div className="bg-purple-50 border border-purple-200 rounded-lg p-4 mb-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
              <svg className="w-5 h-5 text-purple-600 mr-2" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M3 3a1 1 0 000 2v8a2 2 0 002 2h2.586l-1.293 1.293a1 1 0 101.414 1.414L10 15.414l2.293 2.293a1 1 0 001.414-1.414L12.414 15H15a2 2 0 002-2V5a1 1 0 100-2H3zm11.707 4.707a1 1 0 00-1.414-1.414L10 9.586 8.707 8.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l2-2z" clipRule="evenodd" />
              </svg>
              Comparaison personnalisée
            </h2>
            <div className="flex flex-col md:flex-row gap-4 items-end">
              <div className="flex-1">
                <label className="block text-sm font-medium text-gray-700 mb-2">Version 1</label>
                <select
                  value={selectedV1 ?? ''}
                  onChange={(e) => setSelectedV1(e.target.value ? parseInt(e.target.value) : null)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 focus:border-purple-500 focus:ring-purple-200 focus:outline-none bg-white"
                >
                  <option value="">-- Sélectionner une version --</option>
                  {versions?.versions.map((v) => (
                    <option key={v.version} value={v.version}>
                      v{v.version} - {getSupervisionMode(v)} - Score: {v.score_moyen.toFixed(1)}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex-1">
                <label className="block text-sm font-medium text-gray-700 mb-2">Version 2</label>
                <select
                  value={selectedV2 ?? ''}
                  onChange={(e) => setSelectedV2(e.target.value ? parseInt(e.target.value) : null)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 focus:border-purple-500 focus:ring-purple-200 focus:outline-none bg-white"
                >
                  <option value="">-- Sélectionner une version --</option>
                  {versions?.versions.map((v) => (
                    <option key={v.version} value={v.version}>
                      v{v.version} - {getSupervisionMode(v)} - Score: {v.score_moyen.toFixed(1)}
                    </option>
                  ))}
                </select>
              </div>
              <button
                onClick={() => {
                  if (selectedV1 && selectedV2 && selectedV1 !== selectedV2) {
                    compareVersions(selectedV1, selectedV2)
                  }
                }}
                disabled={!selectedV1 || !selectedV2 || selectedV1 === selectedV2}
                className="px-6 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition font-semibold whitespace-nowrap"
              >
                Comparer les versions
              </button>
              {selectedV1 === selectedV2 && selectedV1 !== null && (
                <span className="text-sm text-red-600">Sélectionnez deux versions différentes</span>
              )}
            </div>
          </div>

          {comparing && comparisonData && (
            <div className="mt-8 bg-gradient-to-br from-purple-50 to-blue-50 border border-purple-200 rounded-lg p-6 mb-6">
              <h2 className="text-xl font-semibold mb-6 flex items-center">
                <svg className="w-5 h-5 text-purple-600 mr-2" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M3 3a1 1 0 000 2v8a2 2 0 002 2h2.586l-1.293 1.293a1 1 0 101.414 1.414L10 15.414l2.293 2.293a1 1 0 001.414-1.414L12.414 15H15a2 2 0 002-2V5a1 1 0 100-2H3zm11.707 4.707a1 1 0 00-1.414-1.414L10 9.586 8.707 8.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l2-2z" clipRule="evenodd" />
                </svg>
                Comparaison Version {comparing.v1} vs Version {comparing.v2}
              </h2>
              
              {comparisonData.error ? (
                <div className="text-red-600 p-4 bg-red-50 rounded">{comparisonData.error}</div>
              ) : (
                <>
                  {/* Tableau de comparaison côte à côte */}
                  <div className="bg-white rounded-lg border border-gray-200 overflow-hidden mb-6">
                    <table className="w-full">
                      <thead className="bg-gradient-to-r from-purple-100 to-blue-100 border-b border-gray-300">
                        <tr>
                          <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">Métrique</th>
                          <th className="px-4 py-3 text-center text-sm font-semibold text-blue-700">Version {comparing.v1}</th>
                          <th className="px-4 py-3 text-center text-sm font-semibold text-purple-700">Version {comparing.v2}</th>
                          <th className="px-4 py-3 text-center text-sm font-semibold text-indigo-700">Delta</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-200">
                        <tr className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm font-medium text-gray-700">F1-Score</td>
                          <td className="px-4 py-3 text-center text-sm">
                            <span className="font-semibold text-blue-600">{comparisonData.v1?.f1_score?.toFixed(4) || 'N/A'}</span>
                          </td>
                          <td className="px-4 py-3 text-center text-sm">
                            <span className="font-semibold text-purple-600">{comparisonData.v2?.f1_score?.toFixed(4) || 'N/A'}</span>
                          </td>
                          <td className={`px-4 py-3 text-center text-sm font-bold ${comparisonData.f1_delta > 0 ? 'text-green-600' : comparisonData.f1_delta < 0 ? 'text-red-600' : 'text-gray-600'}`}>
                            {comparisonData.f1_delta > 0 ? '+' : ''}{comparisonData.f1_delta?.toFixed(4)}
                          </td>
                        </tr>
                        <tr className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm font-medium text-gray-700">Precision</td>
                          <td className="px-4 py-3 text-center text-sm">
                            <span className="font-semibold text-blue-600">{comparisonData.v1?.precision?.toFixed(4) || 'N/A'}</span>
                          </td>
                          <td className="px-4 py-3 text-center text-sm">
                            <span className="font-semibold text-purple-600">{comparisonData.v2?.precision?.toFixed(4) || 'N/A'}</span>
                          </td>
                          <td className={`px-4 py-3 text-center text-sm font-bold ${comparisonData.precision_delta > 0 ? 'text-green-600' : comparisonData.precision_delta < 0 ? 'text-red-600' : 'text-gray-600'}`}>
                            {comparisonData.precision_delta > 0 ? '+' : ''}{comparisonData.precision_delta?.toFixed(4)}
                          </td>
                        </tr>
                        <tr className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm font-medium text-gray-700">Recall</td>
                          <td className="px-4 py-3 text-center text-sm">
                            <span className="font-semibold text-blue-600">{comparisonData.v1?.recall?.toFixed(4) || 'N/A'}</span>
                          </td>
                          <td className="px-4 py-3 text-center text-sm">
                            <span className="font-semibold text-purple-600">{comparisonData.v2?.recall?.toFixed(4) || 'N/A'}</span>
                          </td>
                          <td className={`px-4 py-3 text-center text-sm font-bold ${comparisonData.recall_delta > 0 ? 'text-green-600' : comparisonData.recall_delta < 0 ? 'text-red-600' : 'text-gray-600'}`}>
                            {comparisonData.recall_delta > 0 ? '+' : ''}{comparisonData.recall_delta?.toFixed(4)}
                          </td>
                        </tr>
                        <tr className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm font-medium text-gray-700">Accuracy</td>
                          <td className="px-4 py-3 text-center text-sm">
                            <span className="font-semibold text-blue-600">{comparisonData.v1?.accuracy?.toFixed(4) || 'N/A'}</span>
                          </td>
                          <td className="px-4 py-3 text-center text-sm">
                            <span className="font-semibold text-purple-600">{comparisonData.v2?.accuracy?.toFixed(4) || 'N/A'}</span>
                          </td>
                          <td className={`px-4 py-3 text-center text-sm font-bold ${comparisonData.accuracy_delta > 0 ? 'text-green-600' : comparisonData.accuracy_delta < 0 ? 'text-red-600' : 'text-gray-600'}`}>
                            {comparisonData.accuracy_delta > 0 ? '+' : ''}{comparisonData.accuracy_delta?.toFixed(4)}
                          </td>
                        </tr>
                        <tr className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm font-medium text-gray-700">AUC-ROC</td>
                          <td className="px-4 py-3 text-center text-sm">
                            <span className="font-semibold text-blue-600">{comparisonData.v1?.auc_roc?.toFixed(4) || 'N/A'}</span>
                          </td>
                          <td className="px-4 py-3 text-center text-sm">
                            <span className="font-semibold text-purple-600">{comparisonData.v2?.auc_roc?.toFixed(4) || 'N/A'}</span>
                          </td>
                          <td className={`px-4 py-3 text-center text-sm font-bold ${comparisonData.auc_delta > 0 ? 'text-green-600' : comparisonData.auc_delta < 0 ? 'text-red-600' : 'text-gray-600'}`}>
                            {comparisonData.auc_delta > 0 ? '+' : ''}{comparisonData.auc_delta?.toFixed(4)}
                          </td>
                        </tr>
                        <tr className="hover:bg-gray-50 bg-gradient-to-r from-blue-50 to-purple-50 font-semibold">
                          <td className="px-4 py-3 text-sm font-medium text-gray-700">Score Moyen</td>
                          <td className="px-4 py-3 text-center text-sm">
                            <span className="font-bold text-blue-700">{comparisonData.v1?.score_moyen?.toFixed(1) || 'N/A'}</span>
                          </td>
                          <td className="px-4 py-3 text-center text-sm">
                            <span className="font-bold text-purple-700">{comparisonData.v2?.score_moyen?.toFixed(1) || 'N/A'}</span>
                          </td>
                          <td className={`px-4 py-3 text-center text-sm font-bold ${(comparisonData.v2?.score_moyen || 0) - (comparisonData.v1?.score_moyen || 0) > 0 ? 'text-green-600' : (comparisonData.v2?.score_moyen || 0) - (comparisonData.v1?.score_moyen || 0) < 0 ? 'text-red-600' : 'text-gray-600'}`}>
                            {((comparisonData.v2?.score_moyen || 0) - (comparisonData.v1?.score_moyen || 0)) > 0 ? '+' : ''}{((comparisonData.v2?.score_moyen || 0) - (comparisonData.v1?.score_moyen || 0)).toFixed(1)}
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>

                  {/* Résumé et recommandation */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                    <div className="bg-white p-4 rounded border border-indigo-200">
                      <div className="text-sm font-semibold text-indigo-700 mb-2">🏆 Meilleure Version</div>
                      <div className="text-2xl font-bold text-indigo-600">Version {comparisonData.meilleure_version}</div>
                      {comparisonData.meilleure_version === comparing.v1 && (
                        <p className="text-sm text-gray-600 mt-2">Version 1 surpasse la Version 2 sur les performances globales</p>
                      )}
                      {comparisonData.meilleure_version === comparing.v2 && (
                        <p className="text-sm text-gray-600 mt-2">Version 2 surpasse la Version 1 sur les performances globales</p>
                      )}
                      {comparisonData.meilleure_version !== comparing.v1 && comparisonData.meilleure_version !== comparing.v2 && (
                        <p className="text-sm text-gray-600 mt-2">Les deux versions sont équivalentes en performance</p>
                      )}
                    </div>
                    <div className="bg-white p-4 rounded border border-green-200">
                      <div className="text-sm font-semibold text-green-700 mb-2">💡 Recommandation</div>
                      <p className="text-sm text-gray-700">
                        {comparisonData.meilleure_version === comparing.v1 
                          ? `Conservez la Version ${comparing.v1} ou envisagez un réentraînement avec les hyper-paramètres actuels.` 
                          : comparisonData.meilleure_version === comparing.v2
                          ? `Activez la Version ${comparing.v2} pour bénéficier des meilleures performances.`
                          : 'Les deux versions offrent des performances similaires. Choisissez selon d\'autres critères (interprétabilité, coût computationnel, etc.)'}
                      </p>
                    </div>
                  </div>
                </>
              )}
              
              <button
                onClick={() => {
                  setComparing(null)
                  setComparisonData(null)
                  setSelectedV1(null)
                  setSelectedV2(null)
                }}
                className="mt-4 px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 transition-colors"
              >
                Fermer la comparaison
              </button>
            </div>
          )}

          {displayedVersions.length === 0 ? (
            <div className="rounded-lg border border-dashed border-slate-300 bg-white p-6 text-center text-slate-600">
              Aucune version ne correspond aux filtres. Essayez une autre recherche ou un autre filtre.
            </div>
          ) : (
            <>
              <div className="grid gap-6">
                {pageVersions.map((version) => (
              <div key={version.version} className={`border rounded-lg p-6 ${version.active ? 'border-green-300 bg-green-50' : 'border-gray-200'}`}>
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center">
                    <h3 className="text-xl font-semibold text-gray-900">
                      Version {version.version}
                    </h3>
                    {version.active && (
                      <span className="ml-2 px-2 py-1 bg-green-100 text-green-800 text-xs font-medium rounded">
                        ACTIVE
                      </span>
                    )}
                  </div>
                  <div className="text-right text-sm text-gray-500">
                    {formatDate(version.created_at)}
                  </div>
                </div>

                <div className="mb-4 space-y-2">
                  <p className="text-gray-700">{version.notes}</p>
                  {version.analyst_comment && (
                    <div className="mt-2 p-3 bg-gray-50 border rounded text-sm text-slate-700">
                      <strong>Commentaire analyste:</strong>
                      <div className="mt-1 text-xs text-slate-600 whitespace-pre-wrap">{version.analyst_comment}</div>
                    </div>
                  )}
                  {version.report && (
                    <div className="mt-2">
                      <button
                        onClick={() => setOpenReportVersion(openReportVersion === version.version ? null : version.version)}
                        className="text-sm px-3 py-1 bg-indigo-50 border border-indigo-200 text-indigo-700 rounded hover:bg-indigo-100"
                      >
                        {openReportVersion === version.version ? 'Masquer le rapport' : 'Voir le rapport'}
                      </button>
                    </div>
                  )}
                  <div className="inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold leading-5 bg-slate-100 text-slate-800">
                    {getSupervisionMode(version)}
                  </div>
                  <p className="text-sm text-slate-600">{getSupervisionDescription(version)}</p>
                </div>

{openReportVersion === version.version && version.report && (
  <div className="mt-4 p-4 bg-white border border-gray-100 rounded">
    <div className="mb-4">
      <div className="text-sm font-semibold mb-2">Rapport de changements</div>
      <div className="text-sm text-slate-600">{version.report.summary || 'Aucun résumé disponible'}</div>
    </div>
    
    {/* Display changes in a structured way */}
    {Object.keys(version.report.changes || {}).length > 0 && (
      <div className="space-y-3">
        <div className="text-sm font-medium text-gray-900 mb-2">Modifications détectées :</div>
        <div className="space-y-2">
          {Object.entries(version.report.changes || {}).map(([key, change]) => (
            <div key={key} className="p-3 bg-gray-50 rounded-lg">
              <div className="flex justify-between items-start mb-1">
                <span className="font-medium">{formatReportKey(key)}</span>
                <span className="text-xs text-gray-500">{change.before !== null && change.after !== null ? 'Modifié' : 'Ajouté/Supprimé'}</span>
              </div>
              {change.before !== null && change.after !== null && (
                <div className="flex justify-between text-xs text-gray-600">
                  <span>Avant : {formatReportValue(change.before)}</span>
                  <span>Après : {formatReportValue(change.after)}</span>
                </div>
              )}
              {change.before === null && change.after !== null && (
                <div className="text-xs text-gray-600">Nouveau : {formatReportValue(change.after)}</div>
              )}
              {change.before !== null && change.after === null && (
                <div className="text-xs text-gray-600">Supprimé : {formatReportValue(change.before)}</div>
              )}
            </div>
          ))}
        </div>
      </div>
    )}
    
    {/* Fallback when no changes detected */}
    {Object.keys(version.report.changes || {}).length === 0 && (
      <div className="mt-3 p-3 bg-gray-50 rounded">
        <div className="text-xs font-semibold mb-1">Aucun changement détecté</div>
        {version.report.summary && version.report.summary !== "" && version.report.summary.includes("Error") && (
          <div className="text-xs text-gray-500 mt-1">{version.report.summary}</div>
        )}
      </div>
    )}
  </div>
)}

                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-4">
                  <div className="text-center">
                    <div className={`text-2xl font-bold ${version.f1_score !== null ? 'text-blue-600' : 'text-gray-400'}`}>
                      {formatMetric(version.f1_score)}
                    </div>
                    <div className="text-xs text-gray-500">F1-Score</div>
                    {version.f1_score === null && (
                      <div className="text-xs text-gray-400 mt-1">Non-supervisé</div>
                    )}
                  </div>
                  <div className="text-center">
                    <div className={`text-2xl font-bold ${version.precision !== null ? 'text-green-600' : 'text-gray-400'}`}>
                      {formatMetric(version.precision)}
                    </div>
                    <div className="text-xs text-gray-500">Precision</div>
                    {version.precision === null && (
                      <div className="text-xs text-gray-400 mt-1">Non-supervisé</div>
                    )}
                  </div>
                  <div className="text-center">
                    <div className={`text-2xl font-bold ${version.recall !== null ? 'text-purple-600' : 'text-gray-400'}`}>
                      {formatMetric(version.recall)}
                    </div>
                    <div className="text-xs text-gray-500">Recall</div>
                    {version.recall === null && (
                      <div className="text-xs text-gray-400 mt-1">Non-supervisé</div>
                    )}
                  </div>
                  <div className="text-center">
                    <div className={`text-2xl font-bold ${version.accuracy !== null ? 'text-orange-600' : 'text-gray-400'}`}>
                      {formatMetric(version.accuracy)}
                    </div>
                    <div className="text-xs text-gray-500">Accuracy</div>
                    {version.accuracy === null && (
                      <div className="text-xs text-gray-400 mt-1">Non-supervisé</div>
                    )}
                  </div>
                  <div className="text-center">
                    <div className={`text-2xl font-bold ${version.auc_roc !== null ? 'text-red-600' : 'text-gray-400'}`}>
                      {formatMetric(version.auc_roc)}
                    </div>
                    <div className="text-xs text-gray-500">AUC-ROC</div>
                    {version.auc_roc === null && (
                      <div className="text-xs text-gray-400 mt-1">Non-supervisé</div>
                    )}
                  </div>
                  <div className="text-center">
                    <div className={`text-2xl font-bold ${version.score_moyen > 0 ? 'text-indigo-600' : 'text-gray-400'}`}>
                      {version.score_moyen.toFixed(1)}
                    </div>
                    <div className="text-xs text-gray-500">Score Moyen</div>
                    <div className="text-xs text-gray-400 mt-1">/100</div>
                  </div>
                </div>

                <div className="flex gap-2">
                  {!version.active && (
                    <button
                      onClick={() => activateVersion(version.version)}
                      className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
                    >
                      Activer cette version
                    </button>
                  )}
                  {!version.active && (
                    <button
                      onClick={() => deleteVersion(version.version)}
                      className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 transition-colors"
                    >
                      Supprimer
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className="mt-6 flex flex-col gap-3 items-center justify-between rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-600 md:flex-row">
            <div>
              Affichage {displayedVersions.length === 0 ? 0 : (page - 1) * pageSize + 1} - {Math.min(page * pageSize, displayedVersions.length)} sur {displayedVersions.length} version{displayedVersions.length > 1 ? 's' : ''}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => handlePageChange(page - 1)}
                disabled={page <= 1}
                className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 disabled:cursor-not-allowed disabled:opacity-50 hover:bg-slate-50"
              >
                Précédent
              </button>
              <span className="text-slate-700">Page {page} / {totalPages}</span>
              <button
                onClick={() => handlePageChange(page + 1)}
                disabled={page >= totalPages}
                className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 disabled:cursor-not-allowed disabled:opacity-50 hover:bg-slate-50"
              >
                Suivant
              </button>
            </div>
          </div>
            </>
          )}
        </>
      )}
    </div>
  )
}

export default ModelVersions