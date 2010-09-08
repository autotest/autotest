package autotest.afe;

import com.google.gwt.event.dom.client.HasClickHandlers;
import com.google.gwt.user.client.ui.CheckBox;
import com.google.gwt.user.client.ui.HasText;
import com.google.gwt.user.client.ui.HasValue;

public interface ICheckBox extends HasText, HasValue<Boolean>, HasClickHandlers {
    public void setEnabled(boolean enabled);
    public void setVisible(boolean visible);
    public boolean isVisible();

    public static class CheckBoxImpl extends CheckBox implements ICheckBox {
        public CheckBoxImpl() {}

        public CheckBoxImpl(String label) {
            super(label);
        }
    }
}
