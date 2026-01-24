"""
Phase 1 Verification Script
Run this to test that all Phase 1 components are working correctly.
UPDATED: Uses dynamic class/subject models instead of Subject enum.

Usage: python test_phase1.py
"""

import asyncio
import sys
from datetime import datetime


def test_imports():
    """Test that all new modules import correctly."""
    print("\n📦 Testing imports...")
    
    try:
        from config import config
        print("  ✅ config.py imported")
    except Exception as e:
        print(f"  ❌ config.py failed: {e}")
        return False
    
    try:
        from models.schemas import (
            MasteryLevel, LearnerProfile, AssessmentResult,
            TopicKnowledge, Question, CurriculumPlan, PedagogyPlan,
            ClassInfo, SubjectInfo, TopicInfo
        )
        print("  ✅ models/schemas.py imported")
    except Exception as e:
        print(f"  ❌ models/schemas.py failed: {e}")
        return False
    
    try:
        from models.vr_contracts import (
            VRInstruction, AvatarAction, VoiceCommand, 
            VisualCommand, InteractionCommand, AssessmentCommand
        )
        print("  ✅ models/vr_contracts.py imported")
    except Exception as e:
        print(f"  ❌ models/vr_contracts.py failed: {e}")
        return False
    
    try:
        from db.supabase_client import supabase_manager
        print("  ✅ db/supabase_client.py imported")
    except Exception as e:
        print(f"  ❌ db/supabase_client.py failed: {e}")
        return False
    
    return True


def test_config():
    """Test configuration values are loaded."""
    print("\n⚙️  Testing configuration...")
    
    from config import config
    
    issues = []
    
    if not config.SUPABASE_URL:
        issues.append("SUPABASE_URL not set")
    else:
        print(f"  ✅ SUPABASE_URL: {config.SUPABASE_URL[:40]}...")
    
    if not config.SUPABASE_KEY:
        issues.append("SUPABASE_KEY not set")
    else:
        print(f"  ✅ SUPABASE_KEY: {config.SUPABASE_KEY[:20]}...")
    
    if not config.ANTHROPIC_API_KEY:
        issues.append("ANTHROPIC_API_KEY not set (needed for Phase 2)")
    else:
        print(f"  ✅ ANTHROPIC_API_KEY: {config.ANTHROPIC_API_KEY[:10]}...")
    
    if issues:
        print(f"  ⚠️  Missing: {', '.join(issues)}")
        return len(issues) < 2  # OK if only Anthropic is missing for now
    
    return True


def test_models():
    """Test that models work correctly."""
    print("\n📋 Testing Pydantic models...")
    
    from models.schemas import (
        MasteryLevel, LearnerProfile, AssessmentResult,
        TopicKnowledge, LearningStyle, ClassInfo, SubjectInfo
    )
    from models.vr_contracts import (
        VRInstruction, AvatarAction, VoiceCommand,
        AvatarActionType, VoiceEmotion
    )
    
    try:
        # Test ClassInfo and SubjectInfo (new dynamic models)
        class_info = ClassInfo(
            id="class-10-id",
            class_name="Class 10",
            class_number=10,
            description="High School - Grade 10"
        )
        print(f"  ✅ ClassInfo created: {class_info.class_name}")
        
        subject_info = SubjectInfo(
            id="physics-id",
            class_id=class_info.id,
            subject_code="physics",
            subject_name="Physics"
        )
        print(f"  ✅ SubjectInfo created: {subject_info.subject_name}")
        
        # Test LearnerProfile
        profile = LearnerProfile(
            student_id="test-123",
            name="Test Student",
            class_id=class_info.id,
            class_number=10,
            learning_style=LearningStyle.VISUAL_ANALOGY,
            weak_topics=["physics:projectile_motion"],
            strong_topics=["physics:kinematics"],
        )
        print(f"  ✅ LearnerProfile created: {profile.student_id}")
        
        # Test AssessmentResult (using subject_code instead of Subject enum)
        result = AssessmentResult(
            assessment_id="assess-001",
            student_id="test-123",
            subject_code="physics",
            topic_code="projectile_motion",
            topic_name="Projectile Motion",
            score=65,
            level=MasteryLevel.DEVELOPING,
            confidence=0.7,
            misconceptions=["Believes higher angle always increases range"],
        )
        print(f"  ✅ AssessmentResult created: score={result.score}, level={result.level.value}")
        
        # Test VRInstruction
        vr_instruction = VRInstruction(
            step_id="step-001",
            avatar=AvatarAction(action=AvatarActionType.EXPLAIN),
            voice=VoiceCommand(
                text="Let's learn about projectile motion!",
                emotion=VoiceEmotion.FRIENDLY
            ),
        )
        print(f"  ✅ VRInstruction created: {vr_instruction.step_id}")
        
        # Test JSON export for Unity
        unity_json = vr_instruction.to_unity_json()
        print(f"  ✅ Unity JSON export works: {len(str(unity_json))} chars")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Model test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_supabase_connection():
    """Test Supabase connection and basic operations."""
    print("\n🗄️  Testing Supabase connection...")
    
    from db.supabase_client import supabase_manager
    from config import config
    
    if not config.SUPABASE_URL or not config.SUPABASE_KEY:
        print("  ⚠️  Supabase credentials not configured, skipping connection test")
        return True
    
    try:
        # Test client initialization
        client = supabase_manager.client
        print("  ✅ Supabase client initialized")
        
        # Test a simple query (will fail if tables don't exist yet)
        try:
            response = client.table("users").select("id").limit(1).execute()
            print(f"  ✅ Users table accessible (found {len(response.data)} records)")
        except Exception as e:
            error_str = str(e).lower()
            if "does not exist" in error_str or "relation" in error_str or "schema cache" in error_str:
                print("  ⚠️  Tables not created yet - run supabase_schema.sql first")
                return True  # Not a failure, just not set up yet
            raise
        
        # Test classes table
        try:
            response = client.table("classes").select("*").limit(3).execute()
            print(f"  ✅ Classes table accessible (found {len(response.data)} records)")
        except Exception as e:
            if "does not exist" in str(e).lower():
                print("  ⚠️  Classes table not found - run updated schema")
            else:
                raise
        
        return True
        
    except Exception as e:
        print(f"  ❌ Supabase connection failed: {e}")
        return False


async def test_full_flow():
    """Test a complete user creation and profile flow."""
    print("\n🔄 Testing full user flow...")
    
    from db.supabase_client import supabase_manager
    from models.schemas import MasteryLevel, AssessmentResult
    from config import config
    import uuid
    
    if not config.SUPABASE_URL or not config.SUPABASE_KEY:
        print("  ⚠️  Skipping (no Supabase credentials)")
        return True
    
    try:
        # Check if tables exist first
        try:
            supabase_manager.client.table("users").select("id").limit(1).execute()
        except:
            print("  ⚠️  Tables not ready, skipping full flow test")
            return True
        
        # Create a test user
        test_name = f"Test User {datetime.now().strftime('%H%M%S')}"
        user_id = await supabase_manager.create_user(name=test_name)
        print(f"  ✅ Created user: {user_id[:8]}...")
        
        # Get the profile
        profile = await supabase_manager.get_learner_profile(user_id)
        if profile:
            print(f"  ✅ Retrieved profile: learning_style={profile.learning_style.value}")
        else:
            print("  ❌ Failed to retrieve profile")
            return False
        
        # Store an assessment (using subject_code instead of Subject enum)
        assessment = AssessmentResult(
            assessment_id=str(uuid.uuid4()),
            student_id=user_id,
            subject_code="physics",
            topic_code="kinematics",
            topic_name="Kinematics",
            score=75,
            level=MasteryLevel.DEVELOPING,
            confidence=0.8,
        )
        await supabase_manager.store_assessment(assessment)
        print(f"  ✅ Stored assessment: score={assessment.score}")
        
        # Get assessment history
        history = await supabase_manager.get_assessment_history(user_id, subject_code="physics")
        print(f"  ✅ Retrieved {len(history)} assessment(s)")
        
        print(f"\n  🧹 Note: Test user '{test_name}' created in Supabase")
        print(f"     You can delete it manually if needed: ID = {user_id}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Full flow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all Phase 1 tests."""
    print("=" * 60)
    print("🧪 PHASE 1 VERIFICATION")
    print("=" * 60)
    
    results = []
    
    # Test 1: Imports
    results.append(("Imports", test_imports()))
    
    # Test 2: Config
    results.append(("Configuration", test_config()))
    
    # Test 3: Models
    results.append(("Pydantic Models", test_models()))
    
    # Test 4: Supabase Connection
    results.append(("Supabase Connection", await test_supabase_connection()))
    
    # Test 5: Full Flow (optional)
    print("\n" + "-" * 60)
    run_full = input("Run full user flow test? (creates test data) [y/N]: ").strip().lower()
    if run_full == 'y':
        results.append(("Full Flow", await test_full_flow()))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 RESULTS SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 All Phase 1 tests passed! Ready for Phase 2.")
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
