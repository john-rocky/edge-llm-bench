#import "SceneDelegate.h"

#import "AppDelegate.h"

@implementation SceneDelegate

- (void)scene:(UIScene*)scene
    willConnectToSession:(UISceneSession*)session
                 options:(UISceneConnectionOptions*)connectionOptions {
  UIViewController* controller = [[UIViewController alloc] init];
  UITextView* textView = [[UITextView alloc] initWithFrame:controller.view.bounds];
  textView.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
  textView.editable = NO;
  textView.font = [UIFont monospacedSystemFontOfSize:11 weight:UIFontWeightRegular];
  [controller.view addSubview:textView];
  self.window = [[UIWindow alloc] initWithWindowScene:(UIWindowScene*)scene];
  self.window.rootViewController = controller;
  [self.window makeKeyAndVisible];
  AppDelegate* app = (AppDelegate*)UIApplication.sharedApplication.delegate;
  app.textView = textView;
  textView.text = app.logText ?: @"ASR bench: waiting for launch arguments...";
}

@end
