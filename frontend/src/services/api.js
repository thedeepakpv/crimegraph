const API_BASE_URL = import.meta.env.VITE_API_URL || '';

export async function checkHealth() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/health`);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.error('Failed to connect to backend:', error);
    throw error;
  }
}

export async function extractDocumentText(file) {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE_URL}/api/documents/extract`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    let errorMsg = `Upload failed with status ${response.status}`;
    try {
      const errorData = await response.json();
      if (errorData && errorData.detail) {
        errorMsg = errorData.detail;
      }
    } catch (_) {
      // Ignore JSON parse error on non-json error responses
    }
    throw new Error(errorMsg);
  }

  return await response.json();
}

export async function extractEntitiesAndRelationships(payload) {
  const response = await fetch(`${API_BASE_URL}/api/extraction/extract`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let errorMsg = `Extraction failed with status ${response.status}`;
    try {
      const errorData = await response.json();
      if (errorData && errorData.detail) {
        errorMsg = errorData.detail;
      }
    } catch (_) {
      // Ignore
    }
    throw new Error(errorMsg);
  }

  return await response.json();
}

export async function getExtractionStatus() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/extraction/status`);
    if (!response.ok) {
      throw new Error(`Status check failed: ${response.status}`);
    }
    return await response.json();
  } catch (err) {
    console.warn('Could not fetch extraction status:', err);
    return { default_mode: 'demo', ai_available: false };
  }
}

export async function getGraphStatus() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/graph/status`);
    if (!response.ok) {
      throw new Error(`Graph status check failed: ${response.status}`);
    }
    return await response.json();
  } catch (err) {
    console.warn('Could not fetch graph status:', err);
    return { status: 'unavailable', message: err.message };
  }
}

export async function ingestIntoGraph(extractionResult) {
  const response = await fetch(`${API_BASE_URL}/api/graph/ingest`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(extractionResult),
  });

  if (!response.ok) {
    let errorMsg = `Graph ingestion failed with status ${response.status}`;
    try {
      const errorData = await response.json();
      if (errorData && errorData.detail) {
        errorMsg = errorData.detail;
      }
    } catch (_) { }
    throw new Error(errorMsg);
  }

  return await response.json();
}

export async function getAvailableFirs() {
  const response = await fetch(`${API_BASE_URL}/api/graph/firs`);
  if (!response.ok) {
    let errorMsg = `Failed to fetch FIR list with status ${response.status}`;
    try {
      const errorData = await response.json();
      if (errorData && errorData.detail) {
        errorMsg = errorData.detail;
      }
    } catch (_) { }
    throw new Error(errorMsg);
  }
  return await response.json();
}

export async function getGraphForFir(firId) {
  const response = await fetch(`${API_BASE_URL}/api/graph/firs/${encodeURIComponent(firId)}`);
  if (!response.ok) {
    let errorMsg = `Failed to fetch graph for '${firId}' (status ${response.status})`;
    try {
      const errorData = await response.json();
      if (errorData && errorData.detail) {
        errorMsg = errorData.detail;
      }
    } catch (_) { }
    throw new Error(errorMsg);
  }
  return await response.json();
}

export async function getHistoricalConnections(firId) {
  const response = await fetch(`${API_BASE_URL}/api/graph/firs/${encodeURIComponent(firId)}/historical-connections`);
  if (!response.ok) {
    let errorMsg = `Failed to fetch historical connections for '${firId}' (status ${response.status})`;
    try {
      const errorData = await response.json();
      if (errorData && errorData.detail) {
        errorMsg = errorData.detail;
      }
    } catch (_) { }
    throw new Error(errorMsg);
  }
  return await response.json();
}

export async function getGraphAnalytics(firId = null) {
  const url = firId
    ? `${API_BASE_URL}/api/graph/firs/${encodeURIComponent(firId)}/analytics`
    : `${API_BASE_URL}/api/graph/analytics`;
  const response = await fetch(url);
  if (!response.ok) {
    let errorMsg = `Failed to fetch graph analytics (status ${response.status})`;
    try {
      const errorData = await response.json();
      if (errorData && errorData.detail) {
        errorMsg = errorData.detail;
      }
    } catch (_) { }
    throw new Error(errorMsg);
  }
  return await response.json();
}


