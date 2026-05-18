import { useState, useCallback, useEffect } from 'react'
import { Upload, X, Check, AlertCircle } from 'lucide-react'

interface UploadedFile {
  file: File
  status: 'pending' | 'uploading' | 'success' | 'error'
  progress: number
  error?: string
  savedPath?: string
}

interface FileUploadZoneProps {
  onUploadComplete: (result: any) => void
  onError?: (error: string) => void
}

const FileUploadZone = ({ onUploadComplete, onError }: FileUploadZoneProps) => {
  const [isDragging, setIsDragging] = useState(false)
  const [files, setFiles] = useState<UploadedFile[]>([])
  const [uploadError, setUploadError] = useState<string | null>(null)

  useEffect(() => {
    if (!uploadError) return
    const timer = window.setTimeout(() => setUploadError(null), 4000)
    return () => window.clearTimeout(timer)
  }, [uploadError])

  // Fichiers attendus (ordre non imposé)
  const EXPECTED_TYPES = [
    { name: 'sinistres', accept: '.xlsx,.xls', label: 'Sinistres (sinistres.xlsx)' },
    { name: 'contrats', accept: '.xlsx,.xls', label: 'Contrats (contrats.xlsx)' },
    { name: 'tiers', accept: '.xlsx,.xls', label: 'Tiers (tiers.xlsx) - optionnel' },
  ]

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
    // Filtrer les Excel uniquement
    const excelFiles = newFiles.filter(f => 
      f.name.match(/\.(xlsx|xls)$/i)
    )

    if (excelFiles.length === 0) {
      const msg = "Veuillez sélectionner des fichiers Excel (.xlsx ou .xls)"
      setUploadError(msg)
      onError?.(msg)
      return
    }

    // Créer les entries
    const uploadEntries: UploadedFile[] = excelFiles.map(file => ({
      file,
      status: 'pending' as const,
      progress: 0,
    }))

    setFiles(prev => [...prev, ...uploadEntries])
  }

  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index))
  }

  const uploadAll = async () => {
    if (files.length < 2) {
      const msg = "Au moins 2 fichiers requis: sinistres et contrats (tiers optionnel)"
      setUploadError(msg)
      onError?.(msg)
      return
    }

    // Marquer tous comme uploading
    setFiles(prev => prev.map(f => ({ ...f, status: 'uploading' as const, progress: 0 })))

    try {
      const formData = new FormData()
      files.forEach(f => {
        formData.append('files', f.file)
      })

      // Ici, appeler l'API
      // Pour le POC, on simule
      const API_URL = (typeof import.meta !== 'undefined' && import.meta?.env?.VITE_API_URL) || 'http://localhost:8000'
      
      const response = await fetch(`${API_URL}/model/upload-data`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        throw new Error(`Erreur ${response.status}: ${response.statusText}`)
      }

      const result = await response.json()

      // Marquer tous comme success
      setFiles(prev => prev.map((f, index) => ({
        ...f,
        status: 'success' as const,
        progress: 100,
        savedPath: result.saved_to?.[index] || 'sauvé',
      })))

      onUploadComplete(result)

    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Erreur upload'
      setUploadError(msg)
      setFiles(prev => prev.map(f => ({
        ...f,
        status: 'error' as const,
        error: msg,
      })))
      onError?.(msg)
    }
  }

  const clearAll = () => {
    setFiles([])
  }

  const getStatusIcon = (status: UploadedFile['status']) => {
    switch (status) {
      case 'pending':
        return <div className="w-5 h-5 rounded-full border-2 border-gray-300" />
      case 'uploading':
        return <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      case 'success':
        return <Check className="w-5 h-5 text-green-500" />
      case 'error':
        return <AlertCircle className="w-5 h-5 text-red-500" />
    }
  }

  return (
    <div className="space-y-4">
      {/* Zone de drag & drop */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => document.getElementById('file-input')?.click()}
        className={`
          border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
          ${isDragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'}
        `}
      >
        <Upload className="w-12 h-12 mx-auto mb-4 text-gray-400" />
        <p className="text-gray-600 font-medium mb-2">
          Déposez vos fichiers Excel ici, ou cliquez pour sélectionner
        </p>
        <p className="text-sm text-gray-500">
          Fichiers attendus: sinistres.xlsx, contrats.xlsx, tiers.xlsx (optionnel)
        </p>
        <input
          id="file-input"
          type="file"
          multiple
          accept=".xlsx,.xls"
          onChange={handleFileSelect}
          className="hidden"
        />
      </div>

      {/* Liste des fichiers ajoutés */}
      {files.length > 0 && (
        <div className="space-y-2">
          <div className="flex justify-between items-center">
            <h4 className="font-medium text-gray-700">Fichiers à uploader ({files.length})</h4>
            <button
              onClick={clearAll}
              className="text-sm text-red-600 hover:text-red-700"
            >
              Tout supprimer
            </button>
          </div>

          {files.map((uploadedFile, index) => (
            <div
              key={index}
              className="flex items-center gap-3 p-3 bg-gray-50 rounded border"
            >
              {getStatusIcon(uploadedFile.status)}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-800 truncate">
                  {uploadedFile.file.name}
                </p>
                <p className="text-xs text-gray-500">
                  {(uploadedFile.file.size / 1024).toFixed(1)} KB
                </p>
                {uploadedFile.error && (
                  <p className="text-xs text-red-600 mt-1">{uploadedFile.error}</p>
                )}
                {uploadedFile.savedPath && (
                  <p className="text-xs text-green-600 mt-1">
                    ✓ Sauvegardé: {uploadedFile.savedPath}
                  </p>
                )}
              </div>
              <button
                onClick={() => removeFile(index)}
                disabled={uploadedFile.status === 'uploading'}
                className="p-1 hover:bg-gray-200 rounded"
              >
                <X className="w-4 h-4 text-gray-500" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Actions */}
      {files.length > 0 && (
        <div className="flex justify-end gap-3 pt-4">
          <button
            onClick={clearAll}
            disabled={files.some(f => f.status === 'uploading')}
            className="px-4 py-2 border border-gray-300 rounded text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            Annuler
          </button>
          <button
            onClick={uploadAll}
            disabled={files.some(f => f.status === 'uploading')}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {files.some(f => f.status === 'uploading') ? 'Upload en cours...' : 'Uploader et sauvegarder'}
          </button>
        </div>
      )}

      {/* Info */}
      <div className="p-3 bg-yellow-50 border border-yellow-200 rounded text-sm text-yellow-800">
        <strong>Note:</strong> Après l'upload, vous devrez lancer un ré-entraînement
        (POST /model/train) pour intégrer ces nouvelles données aux modèles ML.
        Les seuils et poids peuvent être modifiés indépendamment.
      </div>

      {uploadError && (
        <div className="fixed bottom-6 right-6 z-50 max-w-[320px] rounded-lg bg-red-600 text-white shadow-xl">
          <div className="flex items-start justify-between gap-3 p-4">
            <div className="text-sm leading-5">{uploadError}</div>
            <button
              onClick={() => setUploadError(null)}
              className="text-white opacity-80 hover:opacity-100"
              aria-label="Fermer"
            >
              ×
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default FileUploadZone
