# src/voice/command_recognizer.py

"""
Recognize farmer commands from Urdu speech
"""

class VoiceCommandRecognizer:
    """
    Map spoken Urdu to bot commands
    Handles variations and colloquial speech
    """
    
    def __init__(self):
        self.command_mappings = {
            'حالت': ['halat', 'حالت', 'فصل کی حالت', 'crop status', 'meri fasal kaisi hai'],
            'پانی': ['paani', 'پانی', 'پانی دینا', 'irrigation', 'paani dena hai'],
            'کھاد': ['khaad', 'کھاد', 'fertilizer', 'khad chahiye'],
            'قیمت': ['qeemat', 'قیمت', 'price', 'daam kya hai'],
            'parali': ['parali', 'پرالی', 'stubble', 'parali bechni hai'],
            'مدد': ['madad', 'مدد', 'help', 'madad chahiye']
        }
    
    def recognize_command(self, spoken_text):
        """
        Match spoken text to command
        Returns command keyword
        """
        
        spoken_lower = spoken_text.lower().strip()
        
        # Check each command mapping
        for command, variations in self.command_mappings.items():
            for variation in variations:
                if variation in spoken_lower:
                    return command
        
        # If no exact match, try fuzzy matching
        return self.fuzzy_match(spoken_text)
    
    def fuzzy_match(self, text):
        """Fuzzy matching for similar sounding commands"""
        
        from difflib import SequenceMatcher
        
        best_match = None
        best_score = 0
        
        for command, variations in self.command_mappings.items():
            for variation in variations:
                score = SequenceMatcher(None, text.lower(), variation.lower()).ratio()
                
                if score > best_score and score > 0.6:  # 60% similarity
                    best_score = score
                    best_match = command
        
        return best_match

# Usage
recognizer = VoiceCommandRecognizer()

# Test different variations
tests = [
    "meri fasal kaisi hai",
    "paani dena hai kya",
    "khaad chahiye",
    "parali ka rate kya hai"
]

for test in tests:
    command = recognizer.recognize_command(test)
    print(f"'{test}' → {command}")