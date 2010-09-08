package autotest.afe;

import com.google.gwt.event.dom.client.HasClickHandlers;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.HasText;

public interface IButton extends HasText, HasClickHandlers {
    public void setEnabled(boolean enabled);

    public static class ButtonImpl extends Button implements IButton {
        public ButtonImpl() {}

        public ButtonImpl(String html) {
            super(html);
        }
    }
}
