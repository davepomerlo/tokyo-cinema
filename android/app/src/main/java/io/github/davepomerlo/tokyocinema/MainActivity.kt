package io.github.davepomerlo.tokyocinema

import android.annotation.SuppressLint
import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.view.View
import android.view.ViewGroup
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout

/**
 * Tokyo Cinema for Android.
 *
 * The listings live on GitHub Pages and are refreshed by the daily scan, so this
 * app shows that page full screen. The page's own service worker keeps the last
 * listings on the phone for offline use. Links to theaters, eiga.com, IMDb etc.
 * open in the browser.
 */
class MainActivity : Activity() {

    private lateinit var web: WebView
    private lateinit var swipe: SwipeRefreshLayout

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        web = WebView(this).apply {
            layoutParams = ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT
            )
            setBackgroundColor(Color.TRANSPARENT)
            overScrollMode = View.OVER_SCROLL_NEVER
        }
        swipe = SwipeRefreshLayout(this).apply {
            addView(web)
            setColorSchemeColors(getColor(R.color.accent))
            setOnRefreshListener { web.reload() }
        }
        setContentView(swipe)

        with(web.settings) {
            javaScriptEnabled = true
            domStorageEnabled = true
            cacheMode = WebSettings.LOAD_DEFAULT
            mediaPlaybackRequiresUserGesture = true
            setSupportZoom(false)
            userAgentString = "$userAgentString TokyoCinemaAndroid/${BuildConfig.VERSION_NAME}"
        }

        web.webChromeClient = WebChromeClient()
        web.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                val url = request.url.toString()
                if (isAppPage(url)) return false
                openExternally(request.url)
                return true
            }

            override fun onPageFinished(view: WebView, url: String) {
                swipe.isRefreshing = false
            }

            override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                // Only when the app page itself can't load and nothing is saved yet.
                if (request.isForMainFrame && isAppPage(request.url.toString())) {
                    swipe.isRefreshing = false
                    view.loadUrl("file:///android_asset/offline.html")
                }
            }
        }

        if (savedInstanceState != null) {
            web.restoreState(savedInstanceState)
        } else {
            web.loadUrl(startUrl(intent))
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        if (intent.data != null) web.loadUrl(startUrl(intent))
    }

    /** Home-screen shortcuts pass ?lang=en or ?view=theater through to the page. */
    private fun startUrl(intent: Intent?): String {
        val data = intent?.data ?: return BuildConfig.START_URL
        val query = data.encodedQuery ?: return BuildConfig.START_URL
        return "${BuildConfig.APP_PREFIX}?source=android&$query"
    }

    private fun isAppPage(url: String): Boolean =
        url.startsWith(BuildConfig.APP_PREFIX) || url.startsWith("file:///android_asset/")

    private fun openExternally(uri: Uri) {
        try {
            startActivity(Intent(Intent.ACTION_VIEW, uri).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        } catch (e: ActivityNotFoundException) {
            Toast.makeText(this, "No app can open this link", Toast.LENGTH_SHORT).show()
        }
    }

    override fun onResume() {
        super.onResume()
        web.onResume()
        // Let the page refresh the listings if it has been in the background a while.
        web.evaluateJavascript("document.dispatchEvent(new Event('visibilitychange'))", null)
    }

    override fun onPause() {
        web.onPause()
        super.onPause()
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        web.saveState(outState)
    }

    @Deprecated("Back handling for API < 33 and 33+ without predictive back")
    override fun onBackPressed() {
        if (web.canGoBack()) web.goBack() else super.onBackPressed()
    }

    override fun onDestroy() {
        web.destroy()
        super.onDestroy()
    }
}
