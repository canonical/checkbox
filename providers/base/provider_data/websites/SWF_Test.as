// Run: mtasc -swf SWF_Test.swf -main -header 640:480:20 SWF_Test.as
class Test {

    static var app : Test;

    function Test() {
        _root.createTextField("tf",0,0,0,640,480);
        _root.tf.text = "Test";
    }

    static function main(mc) {
        app = new Test();
    }
}
