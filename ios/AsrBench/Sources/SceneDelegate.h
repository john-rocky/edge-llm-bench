#import <UIKit/UIKit.h>

// Owns the one window. iOS 26 and later require the scene lifecycle; an app without it traps at launch.
@interface SceneDelegate : UIResponder <UIWindowSceneDelegate>
@property(strong, nonatomic) UIWindow* window;
@end
