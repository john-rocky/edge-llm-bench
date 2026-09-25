#import <UIKit/UIKit.h>

// Runs one ASR transcription at launch (arguments from devicectl) and hands the log to
// the scene's text view. Everything lives under Documents/asr/ (models, audio, results).
@interface AppDelegate : UIResponder <UIApplicationDelegate>
@property(weak, nonatomic) UITextView* textView;
@property(copy, nonatomic) NSString* logText;
@end
