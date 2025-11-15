/**
 * Document Types
 * Clinical document structures
 */

export type DocumentType =
  | 'admission'
  | 'progress'
  | 'consult'
  | 'operative'
  | 'clinic'
  | 'imaging'
  | 'lab'
  | 'nursing'
  | 'discharge_planning';

export interface ClinicalDocument {
  name: string;
  content: string;
  date: string; // ISO 8601 format
  type: DocumentType;
  metadata?: {
    author?: string;
    specialty?: string;
    [key: string]: any;
  };
}

export interface DocumentUpload {
  file: File;
  type?: DocumentType;
  date?: Date;
}
