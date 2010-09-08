package autotest.afe;

import com.google.gwt.event.dom.client.HasChangeHandlers;
import com.google.gwt.user.client.ui.HasText;
import com.google.gwt.user.client.ui.TextArea;

public interface ITextArea extends HasText, HasChangeHandlers {
    public void setReadOnly(boolean readOnly);

    public static class TextAreaImpl extends TextArea implements ITextArea {}
}
