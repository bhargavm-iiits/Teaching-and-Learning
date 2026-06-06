using UnityEngine;
using UnityEngine.UI;
using System.Collections;

/// <summary>
/// ConnectionStatusUI - Displays backend connection status as popup/overlay
/// 
/// This script provides visual feedback showing whether Unity is connected to the backend.
/// Features:
/// - Connection status popup
/// - Auto-hide timeout
/// - Color coding (green=connected, red=disconnected, yellow=connecting)
/// - Can be placed on any Canvas
/// 
/// Setup:
/// 1. Create a Canvas in your scene
/// 2. Add this script to a Panel on that Canvas
/// 3. Add Text child object for status message
/// 4. Reference this script from BackendManager
/// </summary>
public class ConnectionStatusUI : MonoBehaviour
{
    [SerializeField] private Text statusText;
    [SerializeField] private Image backgroundImage;
    [SerializeField] private float autoHideTime = 5f;
    [SerializeField] private bool showOnConnect = true;
    [SerializeField] private bool showOnError = true;
    
    private CanvasGroup canvasGroup;
    private Coroutine hideCoroutine;
    
    private Color connectedColor = new Color(0.2f, 0.8f, 0.2f, 0.8f);      // Green
    private Color disconnectedColor = new Color(0.8f, 0.2f, 0.2f, 0.8f);    // Red
    private Color connectingColor = new Color(0.8f, 0.8f, 0.2f, 0.8f);      // Yellow
    private Color errorColor = new Color(0.9f, 0.4f, 0.1f, 0.8f);           // Orange
    
    void Start()
    {
        canvasGroup = GetComponent<CanvasGroup>();
        if (canvasGroup == null)
        {
            canvasGroup = gameObject.AddComponent<CanvasGroup>();
        }
        
        // Start hidden
        Hide();
    }
    
    public void ShowConnecting()
    {
        Show("🔄 Connecting to Backend...", connectingColor);
    }
    
    public void ShowConnected(string message = "✅ Connected to Backend")
    {
        Show(message, connectedColor);
        if (showOnConnect)
            StartAutoHide();
    }
    
    public void ShowDisconnected(string message = "❌ Disconnected from Backend")
    {
        Show(message, disconnectedColor);
        if (showOnError)
            StartAutoHide();
    }
    
    public void ShowError(string message)
    {
        Show("⚠️ " + message, errorColor);
        if (showOnError)
            StartAutoHide();
    }
    
    public void ShowSuccess(string message)
    {
        Show("✓ " + message, connectedColor);
        StartAutoHide();
    }
    
    public void ShowWarning(string message)
    {
        Show("⚠️ " + message, connectingColor);
        StartAutoHide();
    }
    
    private void Show(string message, Color color)
    {
        if (statusText != null)
        {
            statusText.text = message;
        }
        
        if (backgroundImage != null)
        {
            backgroundImage.color = color;
        }
        
        if (canvasGroup != null)
        {
            canvasGroup.alpha = 1f;
        }
        
        gameObject.SetActive(true);
    }
    
    public void Hide()
    {
        if (canvasGroup != null)
        {
            canvasGroup.alpha = 0f;
        }
        
        gameObject.SetActive(false);
    }
    
    private void StartAutoHide()
    {
        if (hideCoroutine != null)
            StopCoroutine(hideCoroutine);
        
        hideCoroutine = StartCoroutine(AutoHideCoroutine());
    }
    
    private IEnumerator AutoHideCoroutine()
    {
        yield return new WaitForSeconds(autoHideTime);
        Hide();
    }
}

/// <summary>
/// EnhancedVRBackendConnector - Extended version with UI feedback
/// 
/// This is an enhanced version of VRBackendConnector that includes
/// visual feedback for all connection events.
/// </summary>
public class EnhancedVRBackendConnector : MonoBehaviour
{
    [SerializeField] private string baseUrl = "http://localhost:8000";
    [SerializeField] private int requestTimeout = 30;
    [SerializeField] private ConnectionStatusUI connectionStatusUI;
    
    private string studentId;
    private bool isConnected = false;
    
    // Events
    public delegate void OnResponseReceived(string response);
    public delegate void OnErrorReceived(string error);
    
    public event OnResponseReceived OnStudentCreated;
    public event OnResponseReceived OnOnboardingStarted;
    public event OnResponseReceived OnContentGenerated;
    public event OnResponseReceived OnResponseSubmitted;
    public event OnResponseReceived OnQuizGenerated;
    public event OnResponseReceived OnNotesGenerated;
    public event OnResponseReceived OnChatResponseReceived;
    public event OnErrorReceived OnError;
    
    void Start()
    {
        // Auto-find ConnectionStatusUI if not assigned
        if (connectionStatusUI == null)
        {
            connectionStatusUI = FindObjectOfType<ConnectionStatusUI>();
        }
        
        // Check connection on startup
        Invoke("CheckServerHealth", 1f);
    }
    
    // ================================================================
    // CONNECTION CHECK
    // ================================================================
    
    public void CheckServerHealth()
    {
        StartCoroutine(CheckServerHealthCoroutine());
    }
    
    private IEnumerator CheckServerHealthCoroutine()
    {
        if (connectionStatusUI != null)
            connectionStatusUI.ShowConnecting();
        
        Debug.Log("[VRBackendConnector] Checking server health...");
        
        using (UnityWebRequest request = UnityWebRequest.Get($"{baseUrl}/health"))
        {
            request.downloadHandler = new DownloadHandlerBuffer();
            request.timeout = requestTimeout;
            
            yield return request.SendWebRequest();
            
            if (request.result == UnityWebRequest.Result.Success)
            {
                isConnected = true;
                Debug.Log("✓ Backend Connection: SUCCESS");
                
                if (connectionStatusUI != null)
                    connectionStatusUI.ShowConnected($"✅ Connected to {baseUrl}");
            }
            else
            {
                isConnected = false;
                string errorMsg = $"Connection Failed: {request.error}";
                Debug.LogError("✗ " + errorMsg);
                
                if (connectionStatusUI != null)
                    connectionStatusUI.ShowError($"Backend unreachable: {baseUrl}");
                
                OnError?.Invoke(errorMsg);
            }
        }
    }
    
    // ================================================================
    // STUDENT CREATION
    // ================================================================
    
    public void CreateStudent(string name, string email = "", int classNumber = 10)
    {
        if (connectionStatusUI != null)
            connectionStatusUI.ShowConnecting();
        
        StartCoroutine(CreateStudentCoroutine(name, email, classNumber));
    }
    
    private IEnumerator CreateStudentCoroutine(string name, string email, int classNumber)
    {
        var requestData = new
        {
            name = name,
            email = string.IsNullOrEmpty(email) ? null : email,
            class_number = classNumber
        };
        
        yield return SendPostRequest($"{baseUrl}/students/create", requestData,
            (response) =>
            {
                var result = JsonUtility.FromJson<StudentResponse>(response);
                if (result != null)
                {
                    studentId = result.student_id;
                    Debug.Log($"✓ Student Created: {studentId}");
                    
                    if (connectionStatusUI != null)
                        connectionStatusUI.ShowSuccess($"Student '{name}' Created");
                    
                    OnStudentCreated?.Invoke(response);
                }
            },
            (error) =>
            {
                if (connectionStatusUI != null)
                    connectionStatusUI.ShowError($"Failed to create student");
            });
    }
    
    // ================================================================
    // ONBOARDING
    // ================================================================
    
    public void StartOnboarding(string subjectCode, string topicCode)
    {
        if (string.IsNullOrEmpty(studentId))
        {
            OnError?.Invoke("Student ID not set. Create a student first.");
            if (connectionStatusUI != null)
                connectionStatusUI.ShowError("No student ID. Create student first.");
            return;
        }
        
        if (connectionStatusUI != null)
            connectionStatusUI.ShowConnecting();
        
        StartCoroutine(StartOnboardingCoroutine(subjectCode, topicCode));
    }
    
    private IEnumerator StartOnboardingCoroutine(string subjectCode, string topicCode)
    {
        var requestData = new
        {
            student_id = studentId,
            subject_code = subjectCode,
            topic_code = topicCode
        };
        
        yield return SendPostRequest($"{baseUrl}/onboarding/start", requestData,
            (response) =>
            {
                Debug.Log("✓ Onboarding started");
                if (connectionStatusUI != null)
                    connectionStatusUI.ShowSuccess($"Onboarding Started: {topicCode}");
                OnOnboardingStarted?.Invoke(response);
            },
            (error) =>
            {
                if (connectionStatusUI != null)
                    connectionStatusUI.ShowError("Onboarding failed");
            });
    }
    
    // ================================================================
    // TEACHING CONTENT
    // ================================================================
    
    public void GenerateTeachingContent(string subjectCode, string topicCode)
    {
        if (string.IsNullOrEmpty(studentId))
        {
            OnError?.Invoke("Student ID not set.");
            if (connectionStatusUI != null)
                connectionStatusUI.ShowError("No student ID set");
            return;
        }
        
        if (connectionStatusUI != null)
            connectionStatusUI.ShowConnecting();
        
        StartCoroutine(GenerateTeachingContentCoroutine(subjectCode, topicCode));
    }
    
    private IEnumerator GenerateTeachingContentCoroutine(string subjectCode, string topicCode)
    {
        var requestData = new
        {
            student_id = studentId,
            subject_code = subjectCode,
            topic_code = topicCode
        };
        
        yield return SendPostRequest($"{baseUrl}/teaching/generate-content", requestData,
            (response) =>
            {
                Debug.Log("✓ Teaching content generated");
                if (connectionStatusUI != null)
                    connectionStatusUI.ShowSuccess($"Lesson Generated: {topicCode}");
                OnContentGenerated?.Invoke(response);
            },
            (error) =>
            {
                if (connectionStatusUI != null)
                    connectionStatusUI.ShowError("Content generation failed");
            });
    }
    
    // ================================================================
    // QUIZ & NOTES
    // ================================================================
    
    public void GenerateQuiz(string topic, int classLevel = 10)
    {
        if (connectionStatusUI != null)
            connectionStatusUI.ShowConnecting();
        
        StartCoroutine(GenerateQuizCoroutine(topic, classLevel));
    }
    
    private IEnumerator GenerateQuizCoroutine(string topic, int classLevel)
    {
        var requestData = new { topic = topic, class_level = classLevel };
        
        yield return SendPostRequest($"{baseUrl}/gen/quiz", requestData,
            (response) =>
            {
                Debug.Log("✓ Quiz generated");
                if (connectionStatusUI != null)
                    connectionStatusUI.ShowSuccess($"Quiz Generated: {topic}");
                OnQuizGenerated?.Invoke(response);
            },
            (error) =>
            {
                if (connectionStatusUI != null)
                    connectionStatusUI.ShowError("Quiz generation failed");
            });
    }
    
    public void GenerateNotes(string topic, int classLevel = 10)
    {
        if (connectionStatusUI != null)
            connectionStatusUI.ShowConnecting();
        
        StartCoroutine(GenerateNotesCoroutine(topic, classLevel));
    }
    
    private IEnumerator GenerateNotesCoroutine(string topic, int classLevel)
    {
        var requestData = new { topic = topic, class_level = classLevel };
        
        yield return SendPostRequest($"{baseUrl}/gen/notes", requestData,
            (response) =>
            {
                Debug.Log("✓ Notes generated");
                if (connectionStatusUI != null)
                    connectionStatusUI.ShowSuccess($"Notes Generated: {topic}");
                OnNotesGenerated?.Invoke(response);
            },
            (error) =>
            {
                if (connectionStatusUI != null)
                    connectionStatusUI.ShowError("Notes generation failed");
            });
    }
    
    // ================================================================
    // CHAT
    // ================================================================
    
    public void SendChatQuery(string query)
    {
        if (connectionStatusUI != null)
            connectionStatusUI.ShowConnecting();
        
        StartCoroutine(SendChatQueryCoroutine(query));
    }
    
    private IEnumerator SendChatQueryCoroutine(string query)
    {
        var requestData = new { query = query };
        
        yield return SendPostRequest($"{baseUrl}/chat", requestData,
            (response) =>
            {
                Debug.Log("✓ Chat response received");
                if (connectionStatusUI != null)
                    connectionStatusUI.ShowSuccess("Chat Response Received");
                OnChatResponseReceived?.Invoke(response);
            },
            (error) =>
            {
                if (connectionStatusUI != null)
                    connectionStatusUI.ShowError("Chat query failed");
            });
    }
    
    // ================================================================
    // CORE HTTP REQUEST
    // ================================================================
    
    private IEnumerator SendPostRequest(string url, object requestData, 
        System.Action<string> onSuccess = null, System.Action<string> onError = null)
    {
        string json = JsonUtility.ToJson(requestData);
        byte[] bodyRaw = System.Text.Encoding.UTF8.GetBytes(json);
        
        using (UnityWebRequest request = new UnityWebRequest(url, "POST"))
        {
            request.uploadHandler = new UploadHandlerRaw(bodyRaw);
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");
            request.timeout = requestTimeout;
            
            yield return request.SendWebRequest();
            
            if (request.result == UnityWebRequest.Result.Success)
            {
                string responseText = request.downloadHandler.text;
                Debug.Log($"Response: {responseText}");
                onSuccess?.Invoke(responseText);
            }
            else
            {
                string errorMsg = $"HTTP {request.responseCode}: {request.error}";
                Debug.LogError($"Request failed: {errorMsg}");
                OnError?.Invoke(errorMsg);
                onError?.Invoke(errorMsg);
            }
        }
    }
    
    // ================================================================
    // UTILITY
    // ================================================================
    
    public bool IsConnected() => isConnected;
    public string GetStudentId() => studentId;
    public void SetStudentId(string id) => studentId = id;
    
    public void ResetSession()
    {
        studentId = null;
        if (connectionStatusUI != null)
            connectionStatusUI.ShowWarning("Session Reset");
    }
    
    public void LogStatus()
    {
        Debug.Log($"[VRBackendConnector Status]");
        Debug.Log($"  Server URL: {baseUrl}");
        Debug.Log($"  Connected: {isConnected}");
        Debug.Log($"  Student ID: {(string.IsNullOrEmpty(studentId) ? "NOT SET" : studentId)}");
    }
}

// ================================================================
// DATA CLASSES
// ================================================================

[System.Serializable]
public class StudentResponse
{
    public string student_id;
    public string message;
}

[System.Serializable]
public class OnboardingResponse
{
    public string assessment_id;
    public string[] questions;
}

[System.Serializable]
public class TeachingContentResponse
{
    public string scene_id;
    public string lesson;
    public string vr_script;
}

[System.Serializable]
public class QuizResponse
{
    public string[] questions;
    public string[] answers;
}

[System.Serializable]
public class NotesResponse
{
    public string notes;
    public string summary;
}

[System.Serializable]
public class ChatResponse
{
    public string answer;
    public string[] sources;
}
