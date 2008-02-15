package afeclient.client;

import com.google.gwt.user.client.ui.Label;
import com.google.gwt.user.client.ui.PopupPanel;

/**
 * A singleton class to manage popup notifications, including error messages and
 * the "loading..." box.
 */
public class NotifyManager {
    // singleton
    public static final NotifyManager theInstance = new NotifyManager();
    
    class NotifyBox {
        protected PopupPanel panel;
        protected Label message = new Label();
        
        public NotifyBox(boolean autoHide) {
            message.setStyleName("notify");
            panel = new PopupPanel(autoHide);
            panel.add(message);
        }
        
        public void addStyle(String style) {
            message.addStyleName(style);
        }
        
        public void hide() {
            panel.hide();
        }
        
        public void show() {
            panel.setPopupPosition(0, 0);
            panel.show();
        }
        
        public void showMessage(String messageString) {
            message.setText(messageString);
            show();
        }
    }
    
    protected NotifyBox errorNotify = new NotifyBox(true);
    protected NotifyBox messageNotify = new NotifyBox(true);
    protected NotifyBox loadingNotify = new NotifyBox(false);
    
    private NotifyManager() {
        errorNotify.addStyle("error");
    }
    
    /**
     * Should be called a page loading time.
     */
    public void initialize() {
        errorNotify.hide();
        messageNotify.hide();
    }
    
    public static NotifyManager getInstance() {
        return theInstance;
    }
    
    /**
     * Show an error message.
     */
    public void showError(String error) {
        errorNotify.showMessage(error);
    }
    
    /**
     * Show a notification message.
     */
    public void showMessage(String message) {
        messageNotify.showMessage(message);
    }
    
    /**
     * Set whether the loading box is displayed or not.
     */
    public void setLoading(boolean visible) {
        if (visible)
            loadingNotify.showMessage("Loading...");
        else
            loadingNotify.hide();
    }
}
