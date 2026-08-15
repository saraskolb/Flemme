import SwiftUI

struct ContentView: View {
    var body: some View {
        FlemmeWebView(url: AppConfig.flemmeURL)
    }
}
