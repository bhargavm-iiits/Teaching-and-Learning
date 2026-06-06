using UnityEngine;
using UnityEngine.UI;
using System.Collections;

/// <summary>
/// BackendConnectionDiagnostic - Test and debug backend connection
/// 
/// This script helps you test the backend connection and diagnose issues.
/// It shows a simple UI with buttons to test each operation.
/// 
/// Setup:
/// 1. Create an empty GameObject named "Diagnostics"
/// 2. Add this script to it
/// 3. The UI will auto-create in the top-left corner
/// </summary>
public class BackendConnectionDiagnostic : MonoBehaviour
{
    private EnhancedVRBackendConnector connector;
    private Canvas diagnosticCanvas;
    private Text diagnosticText;
    private bool showDiagnostics = true;
    
    void Start()
    {
        // Find the connector
        connector = FindObjectOfType<EnhancedVRBackendConnector>();
        
        if (connector == null)
        {
            Debug.LogError("EnhancedVRBackendConnector not found in scene!");
            return;
        }
        
        // Create diagnostic UI
        CreateDiagnosticUI();
        
        // Subscribe to events
        SubscribeToEvents();
        
        Debug.Log("═══════════════════════════════════════════════════");
        Debug.Log("Backend Connection Diagnostic Started");
        Debug.Log("═══════════════════════════════════════════════════");
        Debug.Log("Press 'D' to toggle diagnostic panel");
        Debug.Log("Check the top-left corner of the screen");
        Debug.Log("═══════════════════════════════════════════════════");
    }
    
    void Update()
    {
        // Toggle diagnostics with 'D' key
        if (Input.GetKeyDown(KeyCode.D))
        {
            showDiagnostics = !showDiagnostics;
            if (diagnosticCanvas != null)
                diagnosticCanvas.gameObject.SetActive(showDiagnostics);
        }
        
        // Test commands
        if (Input.GetKeyDown(KeyCode.H))
        {
            Log("Testing Health Check...");
            connector.CheckServerHealth();
        }
        
        if (Input.GetKeyDown(KeyCode.C))
        {
            Log("Creating test student...");
            connector.CreateStudent("TestStudent_" + Random.Range(1000, 9999), 
                                   "test@example.com", 10);
        }
        
        if (Input.GetKeyDown(KeyCode.Q))
        {
            Log("Generating quiz...");
            connector.GenerateQuiz("Test Topic", 10);
        }
        
        if (Input.GetKeyDown(KeyCode.N))
        {
            Log("Generating notes...");
            connector.GenerateNotes("Test Topic", 10);
        }
        
        if (Input.GetKeyDown(KeyCode.M))
        {
            Log("Sending chat query...");
            connector.SendChatQuery("What is physics?");
        }
    }
    
    private void CreateDiagnosticUI()
    {
        // Create Canvas
        GameObject canvasGO = new GameObject("DiagnosticCanvas");
        diagnosticCanvas = canvasGO.AddComponent<Canvas>();
        diagnosticCanvas.renderMode = RenderMode.ScreenSpaceOverlay;
        
        CanvasScaler scaler = canvasGO.AddComponent<CanvasScaler>();
        scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
        
        // Create Panel
        GameObject panelGO = new GameObject("DiagnosticPanel");
        panelGO.transform.SetParent(canvasGO.transform);
        
        Image panelImage = panelGO.AddComponent<Image>();
        panelImage.color = new Color(0.1f, 0.1f, 0.1f, 0.9f);
        
        RectTransform panelRect = panelGO.GetComponent<RectTransform>();
        panelRect.anchorMin = Vector2.zero;
        panelRect.anchorMax = Vector2.zero;
        panelRect.offsetMin = Vector2.zero;
        panelRect.offsetMax = new Vector2(400, 600);
        
        // Create Text
        GameObject textGO = new GameObject("DiagnosticText");
        textGO.transform.SetParent(panelGO.transform);
        
        diagnosticText = textGO.AddComponent<Text>();
        diagnosticText.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
        diagnosticText.fontSize = 14;
        diagnosticText.fontStyle = FontStyle.Bold;
        diagnosticText.color = Color.white;
        diagnosticText.alignment = TextAnchor.UpperLeft;
        
        RectTransform textRect = textGO.GetComponent<RectTransform>();
        textRect.anchorMin = Vector2.zero;
        textRect.anchorMax = Vector2.one;
        textRect.offsetMin = new Vector2(10, -10);
        textRect.offsetMax = new Vector2(-10, 10);
        
        UpdateDiagnosticText();
    }
    
    private void SubscribeToEvents()
    {
        connector.OnStudentCreated += (response) =>
        {
            Log("✓ Student Created");
        };
        
        connector.OnContentGenerated += (response) =>
        {
            Log("✓ Content Generated");
        };
        
        connector.OnQuizGenerated += (response) =>
        {
            Log("✓ Quiz Generated");
        };
        
        connector.OnNotesGenerated += (response) =>
        {
            Log("✓ Notes Generated");
        };
        
        connector.OnChatResponseReceived += (response) =>
        {
            Log("✓ Chat Response Received");
        };
        
        connector.OnError += (error) =>
        {
            Log($"✗ Error: {error}");
        };
    }
    
    private void UpdateDiagnosticText()
    {
        if (diagnosticText == null) return;
        
        string status = connector.IsConnected() ? "✓ CONNECTED" : "✗ DISCONNECTED";
        string studentId = connector.GetStudentId() ?? "Not Set";
        
        string text = $@"
╔══ BACKEND CONNECTION TEST ══╗

Status: {status}

Student ID: {studentId}

═══ KEYBOARD SHORTCUTS ═══

[H] Health Check
[C] Create Student
[Q] Generate Quiz
[N] Generate Notes
[M] Send Chat Query
[D] Toggle Panel

═══ EXAMPLE OUTPUT ═══
{string.Join("\n", GetRecentLogs())}

═══ INSTRUCTIONS ═══
Press a key above to test

Check console for details
Press 'D' to hide/show

════════════════════════════
";
        diagnosticText.text = text;
    }
    
    private void Log(string message)
    {
        Debug.Log("[Diagnostic] " + message);
        UpdateDiagnosticText();
    }
    
    private static Queue<string> logQueue = new Queue<string>();
    
    private Queue<string> GetRecentLogs()
    {
        return logQueue;
    }
}

/// <summary>
/// Quick Connection Test - Attach to any GameObject for instant testing
/// 
/// When the scene starts, it automatically:
/// 1. Checks server health
/// 2. Attempts to create a test student
/// 3. Logs results to console
/// </summary>
public class QuickConnectionTest : MonoBehaviour
{
    void Start()
    {
        Debug.Log("═══════════════════════════════════════════════════");
        Debug.Log("QUICK CONNECTION TEST");
        Debug.Log("═══════════════════════════════════════════════════");
        
        StartCoroutine(RunTests());
    }
    
    private IEnumerator RunTests()
    {
        Debug.Log("[TEST 1] Checking server health...");
        var connector = FindObjectOfType<EnhancedVRBackendConnector>();
        
        if (connector == null)
        {
            Debug.LogError("❌ EnhancedVRBackendConnector not found!");
            yield break;
        }
        
        // Test 1: Health Check
        connector.CheckServerHealth();
        yield return new WaitForSeconds(2);
        
        if (connector.IsConnected())
        {
            Debug.Log("✅ [TEST 1] Server is reachable!");
            
            // Test 2: Create Student
            Debug.Log("[TEST 2] Creating test student...");
            connector.OnStudentCreated += (response) =>
            {
                Debug.Log("✅ [TEST 2] Student created successfully!");
                Debug.Log("Response: " + response);
            };
            
            connector.OnError += (error) =>
            {
                Debug.LogError("❌ [TEST 2] Failed to create student: " + error);
            };
            
            connector.CreateStudent("TestStudent", "test@test.com", 10);
        }
        else
        {
            Debug.LogError("❌ [TEST 1] Cannot reach server. Check:");
            Debug.LogError("  - Is FastAPI running? (python main.py)");
            Debug.LogError("  - Is port 8000 correct?");
            Debug.LogError("  - Is network accessible?");
        }
        
        yield return new WaitForSeconds(3);
        
        Debug.Log("═══════════════════════════════════════════════════");
        Debug.Log("TESTS COMPLETE");
        Debug.Log("═══════════════════════════════════════════════════");
    }
}

/// <summary>
/// Connection Status Logger - Logs connection events to console
/// </summary>
public class ConnectionStatusLogger : MonoBehaviour
{
    void Start()
    {
        var connector = FindObjectOfType<EnhancedVRBackendConnector>();
        
        if (connector == null)
        {
            Debug.LogError("Connector not found!");
            return;
        }
        
        Debug.Log("═══════════════════════════════════════════════════");
        Debug.Log("CONNECTION LOGGER ACTIVE");
        Debug.Log("═══════════════════════════════════════════════════");
        
        // Log all events
        connector.OnStudentCreated += LogEvent("Student Created");
        connector.OnOnboardingStarted += LogEvent("Onboarding Started");
        connector.OnContentGenerated += LogEvent("Content Generated");
        connector.OnResponseSubmitted += LogEvent("Response Submitted");
        connector.OnQuizGenerated += LogEvent("Quiz Generated");
        connector.OnNotesGenerated += LogEvent("Notes Generated");
        connector.OnChatResponseReceived += LogEvent("Chat Response");
        connector.OnError += (error) => Debug.LogError($"❌ ERROR: {error}");
    }
    
    private EnhancedVRBackendConnector.OnResponseReceived LogEvent(string eventName)
    {
        return (response) =>
        {
            Debug.Log($"✓ {eventName}: {response}");
        };
    }
}
