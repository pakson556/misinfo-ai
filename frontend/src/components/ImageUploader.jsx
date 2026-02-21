// frontend/components/ImageUploader.jsx
import React, { useState } from 'react';
import { Upload, Image as ImageIcon, AlertCircle, CheckCircle, XCircle, HelpCircle, FileText } from 'lucide-react';

export default function ImageUploader({ onImageSelect, onAnalyze, isAnalyzing }) {
  const [image, setImage] = useState(null);
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState('');
  const [dragActive, setDragActive] = useState(false);
  const [showTips, setShowTips] = useState(false);

  const handleImageChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      validateAndSetImage(file);
    }
  };

  const validateAndSetImage = (file) => {
    setError('');
    
    // Check file type
    const validTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp'];
    if (!validTypes.includes(file.type)) {
      setError('Please upload an image file (PNG, JPG, JPEG, GIF, WEBP)');
      return;
    }
    
    // Check file size (10MB limit)
    if (file.size > 10 * 1024 * 1024) {
      setError('File size must be less than 10MB');
      return;
    }
    
    setImage(file);
    onImageSelect(file);
    
    // Create preview
    const reader = new FileReader();
    reader.onloadend = () => {
      setPreview(reader.result);
    };
    reader.readAsDataURL(file);
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    const file = e.dataTransfer.files?.[0];
    if (file) {
      validateAndSetImage(file);
    }
  };

  const clearImage = () => {
    setImage(null);
    setPreview(null);
    onImageSelect(null);
  };

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <ImageIcon className="w-5 h-5 text-gray-700" />
          <h2 className="font-semibold text-gray-900">Image Analysis with OCR</h2>
        </div>
        <button
          onClick={() => setShowTips(!showTips)}
          className="p-1 hover:bg-gray-100 rounded-full transition-colors"
          title="Show tips"
        >
          <HelpCircle className="w-5 h-5 text-gray-400" />
        </button>
      </div>
      
      {/* Tips Section */}
      {showTips && (
        <div className="mb-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <h3 className="text-sm font-medium text-blue-800 mb-2 flex items-center gap-1">
            <FileText className="w-4 h-4" />
            Tips for best results:
          </h3>
          <ul className="text-xs text-blue-700 space-y-2 list-disc list-inside">
            <li>Use clear, high-contrast screenshots</li>
            <li>Avoid images with complex backgrounds</li>
            <li>Ensure text is horizontal and not skewed</li>
            <li>Minimum text size: 12pt for best accuracy</li>
            <li>Supported formats: PNG, JPG, JPEG, GIF, WEBP</li>
            <li>Maximum file size: 10MB</li>
          </ul>
          <div className="mt-3 p-2 bg-yellow-50 border border-yellow-200 rounded">
            <p className="text-xs text-yellow-700 flex items-start gap-1">
              <AlertCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
              <span>First time using OCR? Make sure Tesseract is installed on your system.</span>
            </p>
          </div>
        </div>
      )}
      
      {/* Upload Area */}
      {!preview ? (
        <div
          className={`relative border-2 border-dashed rounded-lg transition-colors ${
            dragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'
          }`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          <input
            type="file"
            accept="image/png,image/jpeg,image/jpg,image/gif,image/webp"
            onChange={handleImageChange}
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
            disabled={isAnalyzing}
          />
          <div className="p-8 text-center">
            <Upload className="w-10 h-10 text-gray-400 mx-auto mb-3" />
            <p className="text-sm font-medium text-gray-700 mb-1">
              Click to upload or drag and drop
            </p>
            <p className="text-xs text-gray-500 mb-3">
              PNG, JPG, JPEG, GIF, WEBP up to 10MB
            </p>
            <div className="flex items-center justify-center gap-4 text-xs text-gray-400">
              <span className="flex items-center gap-1">
                <CheckCircle className="w-3 h-3" /> OCR Extraction
              </span>
              <span className="flex items-center gap-1">
                <CheckCircle className="w-3 h-3" /> Multi-model analysis
              </span>
              <span className="flex items-center gap-1">
                <CheckCircle className="w-3 h-3" /> Early detection
              </span>
            </div>
          </div>
        </div>
      ) : (
        /* Preview Area */
        <div className="relative">
          <div className="relative rounded-lg overflow-hidden border border-gray-200">
            <img 
              src={preview} 
              alt="Preview" 
              className="w-full h-48 object-contain bg-gray-50"
            />
            <button
              onClick={clearImage}
              className="absolute top-2 right-2 p-1.5 bg-red-500 text-white rounded-full hover:bg-red-600 transition-colors shadow-lg"
              disabled={isAnalyzing}
            >
              <XCircle className="w-4 h-4" />
            </button>
          </div>
          <div className="mt-2 flex items-center justify-between">
            <p className="text-xs text-gray-500 flex items-center gap-1">
              <CheckCircle className="w-3 h-3 text-green-500" />
              {image?.name} ({(image?.size / 1024).toFixed(1)} KB)
            </p>
            <span className="text-xs text-gray-400">Ready for analysis</span>
          </div>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-xs text-red-600 flex items-start gap-1">
            <AlertCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
            <span>{error}</span>
          </p>
        </div>
      )}

      {/* Analyze Button */}
      {image && (
        <div className="mt-4">
          <button
            onClick={onAnalyze}
            disabled={isAnalyzing}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-gradient-to-r from-blue-600 to-blue-700 text-white rounded-lg text-sm font-medium hover:from-blue-700 hover:to-blue-800 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-sm"
          >
            {isAnalyzing ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
                Extracting text with OCR...
              </>
            ) : (
              <>
                <ImageIcon className="w-4 h-4" />
                Analyze Image with OCR
              </>
            )}
          </button>
          
          {/* OCR Status Note */}
          <p className="text-xs text-gray-400 mt-2 text-center">
            Text will be extracted from image and analyzed by all 3 models
          </p>
        </div>
      )}

      {/* System Check Note */}
      {!image && !error && (
        <div className="mt-4 p-2 bg-gray-50 border border-gray-200 rounded-lg">
          <p className="text-xs text-gray-500 flex items-center gap-1">
            <AlertCircle className="w-3 h-3" />
            <span>Note: OCR requires Tesseract to be installed on the server.</span>
          </p>
        </div>
      )}
    </div>
  );
}