using UnityEngine;
using UnityEngine.Networking;
using System.Collections;
using System;
using System.Collections.Generic;

/// <summary>
/// VRBackendConnector - Connects Unity VR Client to FastAPI Backend
/// 
/// This script handles all communication between Unity and the Python FastAPI backend.
/// It provides methods for:
/// - Student creation and management
/// - Onboarding assessments
/// - Lesson content generation
/// - Real-time feedback submission
/// - Quiz and notes generation
/// 
/// Usage:
/// 1. Attach this script to a GameObject in your scene
/// 2. Call methods like CreateStudent(), GenerateTeachingContent(), etc.
/// 3. Subscribe to events to handle responses
/// 
/// Example:
/// connector.CreateStudent("John", "john@example.com", 10);
/// connector.OnStudentCreated += (response) => Debug.Log(response);
/// </summary>
public class VRBackendConnector : MonoBehaviour
{
    [SerializeField] private string baseUrl = "http://localhost:8000";
    [SerializeField] private int requestTimeout = 30;
    
    private string studentId;
    private string currentLessonId;
    private string currentAssessmentId;
    
    // ================================================================
    // EVENTS - Subscribe to these for response handling
    // ================================================================
    public delegate void OnResponseReceived(string response);
    public delegate void OnErrorReceived(string error);
    public delegate void OnDataReceived<T>(T data);
    
    public event OnResponseReceived OnStudentCreated;
    public event OnResponseReceived OnOnboardingStarted;
    public event OnResponseReceived OnContentGenerated;
    public event OnResponseReceived OnResponseSubmitted;
    public event OnResponseReceived OnQuizGenerated;
    public event OnResponseReceived OnNotesGenerated;
    public event OnResponseReceived OnChatResponseReceived;
    public event OnErrorReceived OnError;
    
    // ================================================================
    // INITIALIZATION & CONFIGURATION
    // ================================================================
    
    public void SetServerUrl(string url)
    {
        baseUrl = url;
        Debug.Log($"Server URL updated to: {baseUrl}");
    }
    
    public void SetStudentId(string id)
    {
        studentId = id;
        Debug.Log($"Student ID set to: {studentId}");
    }
    
    public string GetStudentId()
    {
        return studentId;
    }
    
    // ================================================================
    // 1. STUDENT MANAGEMENT
    // ================================================================
    
    public void CreateStudent(string name, string email = "", int classNumber = 10)
    {
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
                    OnStudentCreated?.Invoke(response);
                }
            });
    }
    
    // ================================================================
    // 2. ONBOARDING & ASSESSMENT
    // ================================================================
    
    public void StartOnboarding(string subjectCode, string topicCode)
    {
        if (string.IsNullOrEmpty(studentId))
        {
            OnError?.Invoke("Student ID not set. Create a student first.");
            return;
        }
        
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
                OnOnboardingStarted?.Invoke(response);
            });
    }
    
    public void SubmitOnboardingResponse(string assessmentId, List<string> responses)
    {
        if (string.IsNullOrEmpty(studentId))
        {
            OnError?.Invoke("Student ID not set.");
            return;
        }
        
        StartCoroutine(SubmitOnboardingCoroutine(assessmentId, responses));
    }
    
    private IEnumerator SubmitOnboardingCoroutine(string assessmentId, List<string> responses)
    {
        var requestData = new
        {
            assessment_id = assessmentId,
            student_id = studentId,
            subject_code = "GENERAL",
            topic_code = "GENERAL",
            questions = new string[] { },
            responses = responses.ToArray()
        };
        
        yield return SendPostRequest($"{baseUrl}/onboarding/submit", requestData,
            (response) =>
            {
                Debug.Log("✓ Onboarding responses submitted");
                OnResponseSubmitted?.Invoke(response);
            });
    }
    
    // ================================================================
    // 3. TEACHING CONTENT GENERATION
    // ================================================================
    
    public void GenerateTeachingContent(string subjectCode, string topicCode)
    {
        if (string.IsNullOrEmpty(studentId))
        {
            OnError?.Invoke("Student ID not set. Create a student first.");
            return;
        }
        
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
                OnContentGenerated?.Invoke(response);
            });
    }
    
    // ================================================================
    // 4. STUDENT RESPONSE & FEEDBACK
    // ================================================================
    
    public void SubmitStudentResponse(string lessonId, string response)
    {
        if (string.IsNullOrEmpty(studentId))
        {
            OnError?.Invoke("Student ID not set.");
            return;
        }
        
        StartCoroutine(SubmitStudentResponseCoroutine(lessonId, response));
    }
    
    private IEnumerator SubmitStudentResponseCoroutine(string lessonId, string response)
    {
        var requestData = new
        {
            student_id = studentId,
            lesson_id = lessonId,
            response = response
        };
        
        yield return SendPostRequest($"{baseUrl}/teaching/submit-response", requestData,
            (resp) =>
            {
                Debug.Log("✓ Student response submitted");
                OnResponseSubmitted?.Invoke(resp);
            });
    }
    
    // ================================================================
    // 5. QUIZ GENERATION
    // ================================================================
    
    public void GenerateQuiz(string topic, int classLevel = 10)
    {
        StartCoroutine(GenerateQuizCoroutine(topic, classLevel));
    }
    
    private IEnumerator GenerateQuizCoroutine(string topic, int classLevel)
    {
        var requestData = new
        {
            topic = topic,
            class_level = classLevel
        };
        
        yield return SendPostRequest($"{baseUrl}/gen/quiz", requestData,
            (response) =>
            {
                Debug.Log("✓ Quiz generated");
                OnQuizGenerated?.Invoke(response);
            });
    }
    
    // ================================================================
    // 6. NOTES GENERATION
    // ================================================================
    
    public void GenerateNotes(string topic, int classLevel = 10)
    {
        StartCoroutine(GenerateNotesCoroutine(topic, classLevel));
    }
    
    private IEnumerator GenerateNotesCoroutine(string topic, int classLevel)
    {
        var requestData = new
        {
            topic = topic,
            class_level = classLevel
        };
        
        yield return SendPostRequest($"{baseUrl}/gen/notes", requestData,
            (response) =>
            {
                Debug.Log("✓ Notes generated");
                OnNotesGenerated?.Invoke(response);
            });
    }
    
    // ================================================================
    // 7. CHAT & RAG QUERY
    // ================================================================
    
    public void SendChatQuery(string query)
    {
        StartCoroutine(SendChatQueryCoroutine(query));
    }
    
    private IEnumerator SendChatQueryCoroutine(string query)
    {
        var requestData = new { query = query };
        
        yield return SendPostRequest($"{baseUrl}/chat", requestData,
            (response) =>
            {
                Debug.Log("✓ Chat response received");
                OnChatResponseReceived?.Invoke(response);
            });
    }
    
    // ================================================================
    // 8. HEALTH CHECK
    // ================================================================
    
    public void CheckServerHealth()
    {
        StartCoroutine(CheckServerHealthCoroutine());
    }
    
    private IEnumerator CheckServerHealthCoroutine()
    {
        using (UnityWebRequest request = UnityWebRequest.Get($"{baseUrl}/health"))
        {
            request.downloadHandler = new DownloadHandlerBuffer();
            request.timeout = requestTimeout;
            
            yield return request.SendWebRequest();
            
            if (request.result == UnityWebRequest.Result.Success)
            {
                Debug.Log("✓ Server is healthy");
            }
            else
            {
                Debug.LogWarning("✗ Server health check failed");
            }
        }
    }
    
    // ================================================================
    // CORE HTTP REQUEST METHODS
    // ================================================================
    
    private IEnumerator SendPostRequest(string url, object requestData, System.Action<string> onSuccess = null)
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
            
            HandleResponse(request, onSuccess);
        }
    }
    
    private IEnumerator SendGetRequest(string url, System.Action<string> onSuccess = null)
    {
        using (UnityWebRequest request = UnityWebRequest.Get(url))
        {
            request.downloadHandler = new DownloadHandlerBuffer();
            request.timeout = requestTimeout;
            
            yield return request.SendWebRequest();
            
            HandleResponse(request, onSuccess);
        }
    }
    
    private void HandleResponse(UnityWebRequest request, System.Action<string> onSuccess)
    {
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
        }
    }
    
    // ================================================================
    // UTILITY METHODS
    // ================================================================
    
    public void ResetSession()
    {
        studentId = null;
        currentLessonId = null;
        currentAssessmentId = null;
        Debug.Log("Session reset");
    }
    
    public bool IsConnected()
    {
        return !string.IsNullOrEmpty(studentId);
    }
    
    public void LogStatus()
    {
        Debug.Log($"[VRBackendConnector Status]");
        Debug.Log($"  Server URL: {baseUrl}");
        Debug.Log($"  Student ID: {(string.IsNullOrEmpty(studentId) ? "NOT SET" : studentId)}");
        Debug.Log($"  Connected: {IsConnected()}");
    }
}

// ================================================================
// DATA CLASSES FOR SERIALIZATION
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
